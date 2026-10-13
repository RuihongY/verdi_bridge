# MIT licensed. Load once in a licensed Verdi GUI using -play or Tcl source.
namespace eval ::vb {
    variable timer
    variable root
    variable session
    variable source_roots
}
proc ::vb::q {s} {
    set out {"}
    foreach c [split $s ""] {
        scan $c %c n
        if {$c eq "\""} {append out {\"}} elseif {$c eq "\\"} {
            append out {\\}
        } elseif {$n < 32} {append out [format {\u%04x} $n]} else {append out $c}
    }
    append out {"}
    return $out
}
proc ::vb::arr {values} {
    set out {}
    foreach v $values {lappend out [q $v]}
    return "\[[join $out ,]\]"
}
proc ::vb::obj {args} {
    set out {}
    foreach {k v} $args {lappend out "[q $k]:$v"}
    return "\{[join $out ,]\}"
}
proc ::vb::name {s} {
    if {$s eq "" || [string index $s 0] eq "-" || [string length $s] > 4096 ||
        [regexp {[\x00-\x1f]} $s]} {error "invalid HDL name"}
    return $s
}
proc ::vb::signal_exists {w s} {
    name $s
    set cut [string last / $s]
    if {$cut < 0} {error "use an absolute waveform path beginning with /"}
    set scope [string range $s 0 [expr {$cut-1}]]
    set leaf [string range $s [expr {$cut+1}] end]
    set known [wvGetSignalsByScope -win $w $scope]
    if {[lsearch -exact $known $leaf] < 0 && [lsearch -exact $known $s] < 0} {
        error "signal not found: $s; use browse_scope for exact bus ranges"
    }
}
proc ::vb::num {s} {
    if {![regexp {^[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$} $s]} {
        error "expected finite nonnegative number"
    }
    set n [expr {double($s)}]
    if {$n > 1e18} {error "time out of range"}
    return $n
}
proc ::vb::timevalue {w value unit} {
    set scales [dict create fs 1e-15 ps 1e-12 ns 1e-9 us 1e-6 ms 1e-3 s 1]
    if {![dict exists $scales $unit]} {error "unit must be fs/ps/ns/us/ms/s"}
    set native [wvGetWindowTimeUnit -win $w]
    if {![regexp {^([0-9]+(?:\.[0-9]+)?)\s*(fs|ps|ns|us|ms|s)$} $native -> factor suffix]} {
        error "unsupported Verdi time unit: $native"
    }
    return [expr {[num $value]*[dict get $scales $unit]/($factor*[dict get $scales $suffix])}]
}
proc ::vb::arity {argsv n} {
    if {[llength $argsv] != $n} {error "wrong argument count"}
}
proc ::vb::dispatch {op argv} {
    variable source_roots
    set w [wvGetCurrentWindow]
    if {$w eq "" || $w eq "0"} {error "open a waveform in nWave first"}
    switch -- $op {
        status {
            arity $argv 0
            return [obj window [q $w] time_unit [q [wvGetWindowTimeUnit -win $w]] \
                cursor [arr [wvGetCursor -win $w]] viewport [arr [wvGetViewTimeRange -win $w]] \
                signals [arr [wvGetDisplaySignals -win $w -all]]]
        }
        browse {
            arity $argv 1
            set scope [name [lindex $argv 0]]
            if {$scope eq "/"} {
                set scopes [wvGetScope -win $w]
                set signals [wvGetSignalsByScope -win $w]
            } else {
                set scopes [wvGetScope -win $w $scope]
                set signals [wvGetSignalsByScope -win $w $scope]
            }
            return [obj scope [q $scope] scopes [arr $scopes] signals [arr $signals] names_relative true]
        }
        add_signals {
            if {[llength $argv] < 1 || [llength $argv] > 128} {error "supply 1..128 signals"}
            foreach s $argv {signal_exists $w $s}
            set ok [wvAddSignal -win $w {*}$argv]
            if {!$ok} {error "Verdi could not add requested signals"}
            return [obj signals [arr [wvGetDisplaySignals -win $w -all]]]
        }
        cursor {
            arity $argv 2
            wvSetCursor -win $w [timevalue $w {*}$argv]
            return [obj cursor [arr [wvGetCursor -win $w]] time_unit [q [wvGetWindowTimeUnit -win $w]]]
        }
        window {
            arity $argv 3
            lassign $argv start end unit
            set a [timevalue $w $start $unit]; set b [timevalue $w $end $unit]
            if {$b <= $a} {error "end must exceed start"}
            wvZoom -win $w $a $b
            return [obj viewport [arr [wvGetViewTimeRange -win $w]] time_unit [q [wvGetWindowTimeUnit -win $w]]]
        }
        sample {
            lassign $argv unit radix n
            if {$radix ni {Bin Hex UDec} || ![string is integer -strict $n] || $n < 1 || $n > 128} {
                error "invalid sample configuration"
            }
            set signals [lrange $argv 3 [expr {$n+2}]]
            set times [lrange $argv [expr {$n+3}] end]
            if {[llength $signals] != $n || [llength $times] < 1 || $n*[llength $times] > 1024} {
                error "invalid sample count"
            }
            foreach s $signals {signal_exists $w $s}
            set rows {}
            foreach t $times {
                set native [timevalue $w $t $unit]
                foreach s $signals {
                    name $s
                    set v [wvGetSigValueByTime -win $w $s -format $radix -time $native]
                    if {$v eq ""} {error "no waveform value for $s"}
                    lappend rows [obj signal [q $s] time [q $t] unit [q $unit] value [q $v]]
                }
            }
            return [obj radix [q $radix] samples "\[[join $rows ,]\]"]
        }
        trace_driver {
            arity $argv 1
            set signal [name [lindex $argv 0]]
            set result [srcTraceDriver $signal]
            if {$result eq "0" || $result eq ""} {error "no driver found"}
            return [obj signal [q $signal] driver [arr $result]]
        }
        source {
            arity $argv 3
            lassign $argv signal start count
            name $signal
            if {![string is integer -strict $start] || ![string is integer -strict $count] ||
                $start < 1 || $count < 1 || $count > 200} {error "invalid line range"}
            set file [srcGetFileName $signal]
            if {![file isfile $file]} {error "source not available for $signal"}
            set file [file normalize $file]
            # normalize resolves parent links; resolve a final-component link too.
            for {set hops 0} {[file type $file] eq "link"} {incr hops} {
                if {$hops >= 40} {error "source symlink loop"}
                set target [file readlink $file]
                set file [file normalize [file join [file dirname $file] $target]]
            }
            set allowed 0
            foreach base $source_roots {
                if {$file eq $base || [string first "${base}/" $file] == 0} {set allowed 1}
            }
            if {!$allowed} {error "source is outside VERDI_BRIDGE_SOURCE_ROOTS"}
            set f [open $file r]; set lines {}; set i 0
            try {
                while {[gets $f line] >= 0} {
                    incr i
                    if {$i >= $start} {lappend lines [obj line $i text [q $line]]}
                    if {[llength $lines] >= $count} {break}
                }
            } finally {close $f}
            return [obj file [q $file] definition_line [q [srcGetDefLine $signal]] lines "\[[join $lines ,]\]"]
        }
        goto_source {
            arity $argv 2
            lassign $argv scope line
            name $scope
            if {![string is integer -strict $line] || $line < 1} {error "invalid line"}
            if {![srcSetScope $scope]} {error "scope unavailable"}
            if {![srcGotoLine -select $line]} {error "source navigation failed"}
            return [obj scope [q $scope] line $line]
        }
        default {error "unsupported operation: $op"}
    }
}
proc ::vb::poll {} {
    variable root; variable session; variable timer
    foreach req [lrange [lsort [glob -nocomplain -directory $root *.req]] 0 7] {
        set id [file rootname [file tail $req]]
        if {![regexp {^[a-f0-9]{32}$} $id]} {continue}
        set claimed "${req}.running"
        if {[catch {file rename $req $claimed}]} {continue}
        set code [catch {
            if {[file size $claimed] > 262144} {error "request too large"}
            set f [open $claimed r]
            try {set raw [read $f]} finally {close $f}
            set fields {}
            foreach field [split [string trimright $raw "\n"] "\n"] {
                lappend fields [encoding convertfrom utf-8 [binary decode base64 -strict $field]]
            }
            lassign $fields requested request_id operation
            if {$requested ne $session || $request_id ne $id} {error "stale session or wrong request ID"}
            dispatch $operation [lrange $fields 3 end]
        } result]
        catch {file delete $claimed}
        if {$code} {set body [obj id [q $id] session [q $session] ok false error [q $result]]} else {
            set body [obj id [q $id] session [q $session] ok true result $result]
        }
        # Output failures must not kill the GUI event loop.
        catch {
            set f [open "$root/$id.res.tmp" w]; puts $f $body; close $f
            file rename -force "$root/$id.res.tmp" "$root/$id.res"
        }
    }
    set timer [after 100 ::vb::poll]
}
proc ::vb::start {} {
    variable root; variable session; variable source_roots; variable timer
    if {[info exists timer]} {error "bridge already running in this GUI"}
    if {![info exists ::env(VERDI_BRIDGE_DIR)]} {error "set VERDI_BRIDGE_DIR before launch"}
    set root [file normalize $::env(VERDI_BRIDGE_DIR)]
    if {![file isdirectory $root] || ![file owned $root] ||
        ([file attributes $root -permissions] & 0o77) != 0} {error "bridge directory must be private (0700)"}
    # Exclusive lock prevents two GUIs consuming each other's requests.
    set lock [open "$root/gui.lock" {WRONLY CREAT EXCL} 0o600]
    puts $lock [pid]; close $lock
    set session "[pid]-[clock clicks]"
    set source_roots [list [file normalize [pwd]]]
    if {[info exists ::env(VERDI_BRIDGE_SOURCE_ROOTS)]} {
        set source_roots {}
        foreach p [split $::env(VERDI_BRIDGE_SOURCE_ROOTS) :] {
            if {$p ne ""} {lappend source_roots [file normalize $p]}
        }
    }
    set f [open "$root/session.tmp" w]; puts $f $session; close $f
    file rename -force "$root/session.tmp" "$root/session"
    set timer [after 100 ::vb::poll]
}
proc ::vb::stop {} {
    variable root; variable timer
    if {[info exists timer]} {after cancel $timer; unset timer; file delete "$root/gui.lock"}
}
::vb::start
