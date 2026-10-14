# MIT licensed. Load once in a licensed Verdi GUI using -play or Tcl source.
namespace eval ::vb {
    variable timer
    variable root
    variable session
    variable source_roots
    variable log_roots
    variable scope_cache
    variable poll_ms 10
}
# JSON string escaping in one C-level pass; per-character Tcl loops cost ~0.1 s/MiB
# on the GUI thread.
namespace eval ::vb {
    variable json_map [list "\\" "\\\\" "\"" "\\\""]
    for {set n 0} {$n < 32} {incr n} {lappend json_map [format %c $n] [format {\u%04x} $n]}
    unset n
}
proc ::vb::q {s} {
    variable json_map
    return "\"[string map $json_map $s]\""
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
# JSON true/false from a Tcl condition evaluated in the caller's scope.
proc ::vb::bool {condition} {
    return [expr {[uplevel 1 [list expr $condition]] ? "true" : "false"}]
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
    variable scope_cache
    if {![dict exists $scope_cache $scope]} {
        dict set scope_cache $scope [wvGetSignalsByScope -win $w $scope]
    }
    set known [dict get $scope_cache $scope]
    if {[lsearch -exact $known $leaf] < 0 && [lsearch -exact $known $s] < 0} {
        error "signal not found: $s; use browse_scope for exact bus ranges"
    }
}
# Exact decimal rationals and integer native ticks: no floating-point scaling.
proc ::vb::decimal_ratio {text} {
    if {[string length $text] > 128 ||
        ![regexp {^([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?$} $text -> whole frac exponent]} {
        error "expected finite nonnegative decimal"
    }
    if {$exponent eq ""} {set exponent 0} else {scan $exponent %d exponent}
    if {abs($exponent) > 30} {error "decimal exponent out of range"}
    set digits [string trimleft "$whole$frac" 0]
    if {$digits eq ""} {set digits 0}
    set places [expr {[string length $frac]-$exponent}]
    if {$places < 0} {return [list [expr {$digits * 10**(-$places)}] 1]}
    return [list $digits [expr {10**$places}]]
}
proc ::vb::unit_exp {unit} {
    set exps [dict create fs -15 ps -12 ns -9 us -6 ms -3 s 0]
    if {![dict exists $exps $unit]} {error "unit must be fs/ps/ns/us/ms/s"}
    return [dict get $exps $unit]
}
proc ::vb::native_ratio {w unit} {
    set native [wvGetWindowTimeUnit -win $w]
    if {![regexp {^([0-9]+(?:\.[0-9]+)?)\s*(fs|ps|ns|us|ms|s)$} $native -> factor suffix]} {
        error "unsupported Verdi time unit: $native"
    }
    lassign [decimal_ratio $factor] n d
    if {$n == 0} {error "native tick must be positive"}
    set exp [expr {[unit_exp $suffix]-[unit_exp $unit]}]
    if {$exp >= 0} {set n [expr {$n*10**$exp}]} else {set d [expr {$d*10**(-$exp)}]}
    return [list $n $d]
}
proc ::vb::integer_tick {n d} {
    if {$n % $d != 0} {error "time is not aligned to a native waveform tick"}
    set tick [expr {$n/$d}]
    # The vendor API may use doubles internally. Reject beyond exact integer range.
    if {$tick > 9007199254740991} {error "time exceeds exact vendor tick range (2^53-1)"}
    return $tick
}
proc ::vb::timevalue {w value unit} {
    lassign [decimal_ratio $value] n d
    lassign [native_ratio $w $unit] tn td
    return [integer_tick [expr {$n*$td}] [expr {$d*$tn}]]
}
proc ::vb::returned_tick {text} {
    lassign [decimal_ratio $text] n d
    return [integer_tick $n $d]
}
proc ::vb::decimal_text {n d} {
    set out [expr {$n/$d}]; set rem [expr {$n%$d}]
    if {$rem} {append out .}
    for {set i 0} {$rem && $i < 128} {incr i} {
        set rem [expr {$rem*10}]
        append out [expr {$rem/$d}]
        set rem [expr {$rem%$d}]
    }
    if {$rem} {error "time cannot be represented as finite decimal"}
    return $out
}
proc ::vb::physical_time {w ticks unit} {
    lassign [native_ratio $w $unit] n d
    return [decimal_text [expr {$ticks*$n}] $d]
}
proc ::vb::arity {argsv n} {
    if {[llength $argsv] != $n} {error "wrong argument count"}
}
# A root equal to / or to an ancestor of $HOME would expose ~/.ssh and similar.
proc ::vb::covers_home {path} {
    if {$path eq "/"} {return 1}
    if {![info exists ::env(HOME)] || $::env(HOME) eq ""} {return 0}
    set home [file normalize $::env(HOME)]
    return [expr {$home eq $path || [string first "${path}/" $home] == 0}]
}
proc ::vb::file_roots {label} {
    if {[info exists ::env($label)]} {
        set roots {}
        foreach p [split $::env($label) :] {
            if {$p eq ""} {continue}
            set p [file normalize $p]
            if {[covers_home $p]} {
                error "$label must not contain / or your home directory; list project directories"
            }
            lappend roots $p
        }
        return $roots
    }
    # Default: Verdi's working directory, unless that would expose the home directory.
    set cwd [file normalize [pwd]]
    if {[covers_home $cwd]} {return {}}
    return [list $cwd]
}
proc ::vb::allowed_file {path {kind source}} {
    variable source_roots; variable log_roots
    if {$kind eq "log"} {set roots $log_roots; set label VERDI_BRIDGE_LOG_ROOTS} else {
        set roots $source_roots; set label VERDI_BRIDGE_SOURCE_ROOTS
    }
    if {![llength $roots]} {
        error "no readable roots: set $label (Verdi's working directory is not used when it\
            is / or contains your home directory)"
    }
    if {![file isfile $path]} {error "file unavailable"}
    set path [file normalize $path]
    for {set hops 0} {[file type $path] eq "link"} {incr hops} {
        if {$hops >= 40} {error "source symlink loop"}
        set path [file normalize [file join [file dirname $path] [file readlink $path]]]
    }
    foreach base $roots {
        if {$path eq $base || [string first "${base}/" $path] == 0} {return $path}
    }
    error "file is outside $label"
}
# Read files as bytes and decode per line: UTF-8 when valid, otherwise the GUI's
# system encoding (e.g. GBK). Independent of the locale Verdi was started with.
proc ::vb::open_bytes {path} {
    set f [open $path r]
    fconfigure $f -encoding iso8859-1
    return $f
}
proc ::vb::text {raw} {
    if {![regexp {[\x80-\xff]} $raw]} {return $raw}
    # Tcl 8.6 decodes invalid UTF-8 leniently (caught by the round trip); Tcl 9 raises.
    if {![catch {encoding convertfrom utf-8 $raw} decoded] &&
        [encoding convertto utf-8 $decoded] eq $raw} {return $decoded}
    if {[catch {encoding convertfrom [encoding system] $raw} decoded]} {return $raw}
    return $decoded
}
proc ::vb::read_lines {path start count} {
    if {![string is integer -strict $start] || ![string is integer -strict $count] ||
        $start < 1 || $count < 1 || $count > 200} {error "invalid line range"}
    if {[file size $path] > 8388608} {error "file exceeds 8 MiB read limit"}
    set f [open_bytes $path]; set lines {}; set i 0
    try {
        while {[gets $f line] >= 0} {
            incr i
            if {$i >= $start} {lappend lines [obj line $i text [q [text $line]]]}
            if {[llength $lines] >= $count} {break}
        }
    } finally {close $f}
    return "\[[join $lines ,]\]"
}
proc ::vb::value {w s radix t} {
    if {$radix eq "SDec"} {
        # Request the complete bit width before interpreting two's complement.
        # Vendor 2Com returned an incorrect zero in our real 2022.06 probe.
        set bits [wvGetSigValueByTime -win $w $s -format Bin -lz -time $t]
        if {$bits eq ""} {error "no waveform value for $s"}
        if {![regexp {^[01]+$} $bits]} {return $bits}
        set v [expr "0b$bits"]
        if {[string index $bits 0] eq "1"} {set v [expr {$v - (1 << [string length $bits])}]}
        return $v
    }
    if {$radix eq "Dec"} {set radix UDec}
    set v [wvGetSigValueByTime -win $w $s -format $radix -time $t]
    if {$v eq ""} {error "no waveform value for $s"}
    return $v
}
proc ::vb::child_path {scope child} {
    if {[string index $child 0] eq "/"} {return $child}
    return "[string trimright $scope /]/$child"
}
proc ::vb::dispatch {op argv} {
    variable source_roots; variable scope_cache
    set scope_cache {}
    set w [wvGetCurrentWindow]
    if {$w eq "" || $w eq "0"} {error "open a waveform in nWave first"}
    switch -- $op {
        status {
            arity $argv 0
            set displayed [wvGetDisplaySignals -win $w -all]
            return [obj window [q $w] time_unit [q [wvGetWindowTimeUnit -win $w]] \
                cursor [arr [wvGetCursor -win $w]] viewport [arr [wvGetViewTimeRange -win $w]] \
                signals [arr [lrange $displayed 0 199]] signals_total [llength $displayed] \
                signals_truncated [bool {[llength $displayed] > 200}]]
        }
        browse {
            arity $argv 3
            lassign $argv scope offset limit
            name $scope
            if {![string is integer -strict $offset] || $offset < 0 ||
                ![string is integer -strict $limit] || $limit < 1 || $limit > 2000} {
                error "invalid browse page"
            }
            if {$scope eq "/"} {set args {}} else {set args [list $scope]}
            set scopes [wvGetScope -win $w {*}$args]
            set signals [wvGetSignalsByScope -win $w {*}$args]
            # One page over scopes followed by signals; huge flat scopes stay bounded.
            set ns [llength $scopes]; set end [expr {$offset+$limit}]
            set page_scopes [lrange $scopes $offset [expr {$end-1}]]
            set page_signals [lrange $signals [expr {max(0, $offset-$ns)}] [expr {$end-$ns-1}]]
            set total [expr {$ns+[llength $signals]}]
            set next [expr {$end < $total ? $end : "null"}]
            return [obj scope [q $scope] scopes [arr $page_scopes] signals [arr $page_signals] \
                total_scopes $ns total_signals [llength $signals] next_offset $next \
                names_relative true]
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
            lassign $argv unit radix budget_ms n
            if {$radix ni {Bin Hex UDec Dec SDec} || ![string is integer -strict $n] || $n < 1 ||
                $n > 128 || ![string is integer -strict $budget_ms] || $budget_ms < 1 ||
                $budget_ms > 10000} {
                error "invalid sample configuration"
            }
            set signals [lrange $argv 4 [expr {$n+3}]]
            set times [lrange $argv [expr {$n+4}] end]
            if {[llength $signals] != $n || [llength $times] < 1 || $n*[llength $times] > 1024} {
                error "invalid sample count"
            }
            foreach s $signals {signal_exists $w $s}
            set native {}
            foreach t $times {lappend native [timevalue $w $t $unit]}
            # Signal-major order: Verdi loads a signal on first access, which can take
            # ~0.15 s each in large flat scopes. Stop between signals once the budget
            # is spent, always completing at least one signal.
            set deadline [expr {[clock clicks -milliseconds]+$budget_ms}]
            set rows {}; set pending {}
            foreach s $signals {
                if {[llength $rows] && [clock clicks -milliseconds] >= $deadline} {
                    lappend pending $s; continue
                }
                foreach t $times nt $native {
                    lappend rows [obj signal [q $s] time [q $t] unit [q $unit] \
                        value [q [value $w $s $radix $nt]]]
                }
            }
            return [obj radix [q $radix] samples "\[[join $rows ,]\]" \
                truncated [bool {[llength $pending] > 0}] pending_signals [arr $pending] \
                budget_ms $budget_ms]
        }
        count_changes {
            lassign $argv start end unit budget_ms
            set signals [lrange $argv 4 end]
            if {![string is integer -strict $budget_ms] || $budget_ms < 1 || $budget_ms > 10000 ||
                [llength $signals] < 1 || [llength $signals] > 128} {
                error "invalid count limits"
            }
            set a [timevalue $w $start $unit]; set b [timevalue $w $end $unit]
            if {$b <= $a} {error "end must exceed start"}
            foreach s $signals {signal_exists $w $s}
            set deadline [expr {[clock clicks -milliseconds]+$budget_ms}]
            set cursor [wvGetCursor -win $w]; set view [wvGetViewTimeRange -win $w]
            set rows {}; set any_truncated false
            try {
                foreach s $signals {
                    if {[llength $rows] && [clock clicks -milliseconds] >= $deadline} {
                        set any_truncated true
                        lappend rows [obj signal [q $s] count null complete false \
                            resume_from [q $start]]
                        continue
                    }
                    # Transitions only: no per-change value lookups.
                    set t $a; set count 0; set first ""; set complete true
                    while {1} {
                        if {[clock clicks -milliseconds] >= $deadline} {
                            set complete false; set any_truncated true; break
                        }
                        set next [wvSearchNextBySignal -win $w -delim / $s -time $t]
                        if {[lindex $next 0] ne "1"} {break}
                        set nt [returned_tick [lindex $next 1]]
                        if {$nt <= $t} {error "Verdi transition search did not advance"}
                        if {$nt > $b} {break}
                        if {$first eq ""} {set first $nt}
                        incr count; set t $nt
                    }
                    set fields [list signal [q $s] count $count complete $complete \
                        initial [q [value $w $s Hex $a]] \
                        first_change [expr {$first eq "" ? "null" : [q [physical_time $w $first $unit]]}] \
                        last_change [expr {$count ? [q [physical_time $w $t $unit]] : "null"}]]
                    if {$complete} {
                        lappend fields final [q [value $w $s Hex [expr {$count ? $t : $a}]]]
                    } else {
                        lappend fields resume_from [q [physical_time $w $t $unit]]
                    }
                    lappend rows [obj {*}$fields]
                }
            } finally {
                wvSetCursor -win $w [lindex $cursor 1]
                wvZoom -win $w {*}[lrange $view 1 2]
            }
            return [obj unit [q $unit] interval [arr [list $start $end]] \
                boundary [q "(start, end]; initial is the Hex value at start"] \
                signals "\[[join $rows ,]\]" truncated $any_truncated budget_ms $budget_ms \
                glitches_skipped true]
        }
        sample_on_clock {
            lassign $argv clock start end unit radix edge when max budget_ms
            set signals [lrange $argv 9 end]
            if {$radix ni {Bin Hex UDec Dec SDec} || $edge ni {rising falling both} ||
                $when ni {pre post} || ![string is integer -strict $max] || $max < 1 ||
                ![string is integer -strict $budget_ms] || $budget_ms < 1 || $budget_ms > 10000 ||
                [llength $signals] < 1 || [llength $signals] > 128 ||
                $max*[llength $signals] > 4096} {error "invalid clock sampling limits"}
            set a [timevalue $w $start $unit]; set b [timevalue $w $end $unit]
            if {$b <= $a} {error "end must exceed start"}
            signal_exists $w $clock
            foreach s $signals {signal_exists $w $s}
            set deadline [expr {[clock clicks -milliseconds]+$budget_ms}]
            set cursor [wvGetCursor -win $w]; set view [wvGetViewTimeRange -win $w]
            set rows {}; set t $a; set reason ""
            try {
                while {1} {
                    if {[clock clicks -milliseconds] >= $deadline} {set reason "time budget"; break}
                    set next [wvSearchNextBySignal -win $w -delim / $clock -time $t]
                    if {[lindex $next 0] ne "1"} {break}
                    set nt [returned_tick [lindex $next 1]]
                    if {$nt <= $t} {error "Verdi transition search did not advance"}
                    if {$nt > $b} {break}
                    set level [value $w $clock Bin $nt]
                    if {($level eq "1" && $edge ne "falling") || ($level eq "0" && $edge ne "rising")} {
                        if {[llength $rows] == $max} {set reason "max cycles"; break}
                        # "pre" reads one native tick before the edge: the values flops sample.
                        set st [expr {$when eq "pre" && $nt > 0 ? $nt-1 : $nt}]
                        set values {}
                        foreach s $signals {lappend values [value $w $s $radix $st]}
                        lappend rows [obj time [q [physical_time $w $nt $unit]] \
                            edge [q [expr {$level eq "1" ? "rising" : "falling"}]] \
                            values [arr $values]]
                    }
                    set t $nt
                }
            } finally {
                wvSetCursor -win $w [lindex $cursor 1]
                wvZoom -win $w {*}[lrange $view 1 2]
            }
            return [obj clock [q $clock] unit [q $unit] radix [q $radix] edge [q $edge] \
                sample [q $when] signals [arr $signals] cycles "\[[join $rows ,]\]" \
                truncated [bool {$reason ne ""}] reason [q $reason] \
                resume_from [q [physical_time $w $t $unit]] budget_ms $budget_ms]
        }
        trace_driver {
            arity $argv 1
            set signal [name [lindex $argv 0]]
            set result [srcTraceDriver $signal]
            if {$result eq "0" || $result eq ""} {error "no driver found"}
            set drivers {}
            foreach {scope file line} $result {
                lappend drivers [obj scope [q $scope] file [q $file] line [q $line]]
            }
            return [obj signal [q $signal] driver [arr $result] \
                drivers "\[[join $drivers ,]\]" \
                type_note [q "srcTraceDriver does not provide assignment types"]]
        }
        source {
            arity $argv 3
            lassign $argv signal start count
            name $signal
            set file [allowed_file [srcGetFileName $signal]]
            return [obj file [q $file] definition_line [q [srcGetDefLine $signal]] \
                lines [read_lines $file $start $count]]
        }
        source_file {
            arity $argv 3
            lassign $argv file start count
            set file [allowed_file $file]
            return [obj file [q $file] lines [read_lines $file $start $count]]
        }
        read_log {
            arity $argv 3
            lassign $argv path pattern max
            if {![string is integer -strict $max] || $max < 1 || $max > 200 ||
                [string length $pattern] > 4096} {error "invalid log limits"}
            set path [allowed_file $path log]
            if {[file size $path] > 8388608} {error "log exceeds 8 MiB read limit"}
            set f [open_bytes $path]; set rows {}; set i 0; set truncated false
            try {
                while {[gets $f line] >= 0} {
                    incr i
                    set line [text $line]
                    if {[string first $pattern $line] < 0} {continue}
                    if {[llength $rows] == $max} {set truncated true; break}
                    lappend rows [obj line $i text [q $line]]
                }
            } finally {close $f}
            return [obj file [q $path] pattern [q $pattern] lines "\[[join $rows ,]\]" \
                truncated $truncated matching [q "literal substring, case sensitive"]]
        }
        find_signals {
            arity $argv 6
            lassign $argv pattern scope max depth glob budget_ms
            if {$glob ni {0 1}} {error "glob must be boolean"}
            set glob_pattern [string map {\[ \\[ \] \\]} $pattern]
            name $scope
            if {[string index $scope 0] ne "/" || $pattern eq "" ||
                [string length $pattern] > 4096 || ![string is integer -strict $max] ||
                $max < 1 || $max > 1000 || ![string is integer -strict $depth] ||
                $depth < 0 || $depth > 64 || ![string is integer -strict $budget_ms] ||
                $budget_ms < 1 || $budget_ms > 2000} {error "invalid search limits"}
            set deadline [expr {[clock clicks -milliseconds]+$budget_ms}]
            set queue [list [list $scope 0]]; set head 0; set seen {}; set found {}
            set truncated false; set reasons {}; set visited 0
            while {$head < [llength $queue]} {
                lassign [lindex $queue $head] current level
                incr head
                if {[dict exists $seen $current]} {continue}
                if {[clock clicks -milliseconds] >= $deadline} {
                    set truncated true; lappend reasons "time budget"; break
                }
                dict set seen $current 1
                incr visited
                if {$visited > 2048} {set truncated true; lappend reasons "scope limit"; break}
                if {$current eq "/"} {set args {}} else {set args [list $current]}
                foreach leaf [wvGetSignalsByScope -win $w {*}$args] {
                    set path [child_path $current $leaf]
                    if {(!$glob && [string first $pattern $path] >= 0) ||
                        ($glob && [string match $glob_pattern $path])} {
                        if {[llength $found] == $max} {
                            set truncated true; lappend reasons "max results"; break
                        }
                        lappend found $path
                    }
                }
                if {"max results" in $reasons} {break}
                set children [wvGetScope -win $w {*}$args]
                if {$level == $depth && [llength $children]} {
                    set truncated true; lappend reasons "depth"; continue
                }
                foreach child $children {
                    lappend queue [list [child_path $current $child] [expr {$level+1}]]
                }
            }
            return [obj signals [arr $found] truncated $truncated \
                reasons [arr [lsort -unique $reasons]] visited_scopes $visited \
                depth $depth scope [q $scope] pattern [q $pattern] budget_ms $budget_ms]
        }
        changes {
            lassign $argv start end unit radix max budget_ms
            set signals [lrange $argv 6 end]
            if {![string is integer -strict $budget_ms] || $budget_ms < 1 || $budget_ms > 2000} {
                error "budget_ms must be 1..2000"
            }
            set deadline [expr {[clock clicks -milliseconds]+$budget_ms}]
            if {$radix ni {Bin Hex UDec Dec SDec} || ![string is integer -strict $max] ||
                $max < 1 || $max > 4096 || [llength $signals] < 1 ||
                [llength $signals] > 128 || $max*[llength $signals] > 4096} {
                error "invalid changes limits"
            }
            set a [timevalue $w $start $unit]; set b [timevalue $w $end $unit]
            if {$b <= $a} {error "end must exceed start"}
            set cursor [wvGetCursor -win $w]; set view [wvGetViewTimeRange -win $w]
            set results {}; set any_truncated false; set reasons {}
            try {
                foreach signal $signals {
                    if {[clock clicks -milliseconds] >= $deadline} {
                        set any_truncated true; lappend reasons "time budget"
                        lappend results [obj signal [q $signal] initial null changes {[]} \
                            truncated true reason [q "time budget"] resume_from [q $start]]
                        continue
                    }
                    signal_exists $w $signal
                    set initial [value $w $signal $radix $a]
                    set previous $initial; set t $a; set rows {}; set truncated false; set reason ""
                    while {1} {
                        if {[clock clicks -milliseconds] >= $deadline} {
                            set truncated true; set any_truncated true; set reason "time budget"; break
                        }
                        set next [wvSearchNextBySignal -win $w -delim / $signal -time $t]
                        if {[lindex $next 0] ne "1"} {break}
                        set nt [returned_tick [lindex $next 1]]
                        if {$nt <= $t} {
                            error "Verdi transition search did not advance"
                        }
                        if {$nt > $b} {break}
                        if {[llength $rows] == $max} {set truncated true; set any_truncated true; set reason "max changes"; break}
                        set after [value $w $signal $radix $nt]
                        lappend rows [obj time [q [physical_time $w $nt $unit]] \
                            before [q $previous] after [q $after]]
                        set previous $after; set t $nt
                    }
                    if {$reason ne ""} {lappend reasons $reason}
                    lappend results [obj signal [q $signal] initial [q $initial] \
                        changes "\[[join $rows ,]\]" truncated $truncated \
                        reason [q $reason] resume_from [q [physical_time $w $t $unit]]]
                }
            } finally {
                wvSetCursor -win $w [lindex $cursor 1]
                wvZoom -win $w {*}[lrange $view 1 2]
            }
            return [obj unit [q $unit] radix [q $radix] interval [arr [list $start $end]] \
                boundary [q "(start, end]; initial is the value at start"] \
                signals "\[[join $results ,]\]" truncated $any_truncated \
                reasons [arr [lsort -unique $reasons]] budget_ms $budget_ms glitches_skipped true]
        }
        engine_info {
            # What a headless NPI reader needs to open the same waveform.
            arity $argv 0
            set fsdb [wvGetActiveFileName -win $w]
            if {$fsdb ne ""} {set fsdb [file normalize $fsdb]}
            set env {}
            foreach var {VERDI_HOME SNPSLMD_LICENSE_FILE LM_LICENSE_FILE} {
                if {[info exists ::env($var)]} {lappend env $var [q $::env($var)]}
            }
            return [obj fsdb [q $fsdb] env [obj {*}$env]]
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
    variable timer; variable poll_ms
    # Never let a filesystem error (e.g. a stale NFS handle) end the polling loop.
    if {[catch {poll_once} message]} {catch {puts stderr "verdi-bridge: $message"}}
    set timer [after $poll_ms ::vb::poll]
}
proc ::vb::poll_once {} {
    variable root; variable session
    # Serve one request per tick. Skip foreign *.req names instead of stalling on them.
    foreach req [lsort [glob -nocomplain -directory $root *.req]] {
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
        # Output failures must not kill the GUI event loop. Responses are always
        # UTF-8 so the helper's locale (often C/ASCII over SSH) does not matter.
        catch {
            set f [open "$root/$id.res.tmp" w]
            fconfigure $f -encoding utf-8
            puts $f $body; close $f
            file rename -force "$root/$id.res.tmp" "$root/$id.res"
        }
        break
    }
}
# A lock is stale only if it names this host and a process that no longer exists.
proc ::vb::stale_lock {path} {
    variable timer
    if {[catch {set f [open $path r]; set text [read $f]; close $f}]} {return 0}
    lassign $text pid host
    if {![string is integer -strict $pid] || $host ne [info hostname]} {return 0}
    if {$pid == [pid]} {return [expr {![info exists timer]}]}
    if {[file isdirectory /proc/self]} {return [expr {![file exists /proc/$pid]}]}
    return [catch {exec kill -0 $pid}]
}
proc ::vb::start {} {
    variable root; variable session; variable source_roots; variable log_roots; variable timer; variable poll_ms
    if {[info exists timer]} {error "bridge already running in this GUI"}
    if {[info exists ::env(VERDI_BRIDGE_DIR)] && $::env(VERDI_BRIDGE_DIR) ne ""} {
        set root [file normalize $::env(VERDI_BRIDGE_DIR)]
    } else {
        # Stable default, so the MCP client configuration survives GUI restarts.
        if {![info exists ::env(HOME)]} {error "set VERDI_BRIDGE_DIR before launch"}
        set root [file normalize [file join $::env(HOME) .verdi-bridge session]]
        foreach d [list [file dirname $root] $root] {
            if {![file exists $d]} {file mkdir $d; file attributes $d -permissions 0o700}
        }
    }
    if {[catch {file type $root} type] || $type ne "directory" || ![file owned $root] ||
        ([file attributes $root -permissions] & 0o77) != 0} {
        error "bridge directory must be private (0700) and not a symlink: $root"
    }
    if {[info exists ::env(VERDI_BRIDGE_POLL_MS)]} {
        set poll_ms $::env(VERDI_BRIDGE_POLL_MS)
        if {![string is integer -strict $poll_ms] || $poll_ms < 1 || $poll_ms > 1000} {
            error "VERDI_BRIDGE_POLL_MS must be 1..1000"
        }
    }
    set source_roots [file_roots VERDI_BRIDGE_SOURCE_ROOTS]
    # Log access is independent: default only the simulation working directory.
    set log_roots [file_roots VERDI_BRIDGE_LOG_ROOTS]
    # Exclusive lock prevents two GUIs consuming each other's requests.
    set lockfile "$root/gui.lock"
    if {[file exists $lockfile] && [stale_lock $lockfile]} {file delete $lockfile}
    if {[catch {open $lockfile {WRONLY CREAT EXCL} 0o600} lock]} {
        error "another Verdi GUI uses $root (gui.lock); run ::vb::stop there,\
            or set VERDI_BRIDGE_DIR to a separate private directory"
    }
    puts $lock "[pid] [info hostname]"; close $lock
    # Requests and results of an earlier session can never match the new one.
    foreach old [glob -nocomplain -directory $root *.req *.req.running *.res *.res.tmp *.tmp] {
        if {[regexp {^[a-f0-9]{32}\.} [file tail $old]]} {catch {file delete $old}}
    }
    set session "[pid]-[clock clicks]"
    set f [open "$root/session.tmp" w]; puts $f $session; close $f
    file rename -force "$root/session.tmp" "$root/session"
    set timer [after $poll_ms ::vb::poll]
}
proc ::vb::stop {} {
    variable root; variable timer
    if {[info exists timer]} {after cancel $timer; unset timer; file delete "$root/gui.lock"}
}
::vb::start
