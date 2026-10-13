# Behavioral double for transport tests. This is NOT a vendor simulator.
set cursor 0
set viewport {1 0 1000000}
set signals {}
proc wvGetCurrentWindow {} {return test-window}
proc wvGetWindowTimeUnit {args} {return 1ps}
proc wvGetCursor {args} {return [list 1 $::cursor x 1ps]}
proc wvGetViewTimeRange {args} {return $::viewport}
proc wvGetDisplaySignals {args} {return $::signals}
proc wvSetCursor {args} {set ::cursor [lindex $args 2]; return 1}
proc wvZoom {args} {set ::viewport [list 1 {*}[lrange $args 2 end]]; return 1}
proc wvAddSignal {args} {set ::signals [lrange $args 2 end]; return 1}
proc wvGetScope {args} {
    if {[llength $args] == 2} {return {/tb/dut}}
    if {[lindex $args 2] eq "/tb/dut"} {return {nested}}
    return {}
}
proc wvGetSignalsByScope {args} {
    if {[lindex $args 2] eq "/cache"} {
        if {[info exists ::cache_used]} {error "duplicate scope lookup"}
        set ::cache_used 1
        after 0 {unset ::cache_used}
    }
    set names {ptr[3:0] ptr3 ptr0 ptr: full slow_clk pulse clk signed flat stuck_search}
    for {set i 0} {$i < 16} {incr i} {lappend names s$i}
    if {[info exists ::env(TEST_LITERAL_SIGNAL)]} {lappend names $::env(TEST_LITERAL_SIGNAL)}
    return $names
}
proc wvGetSigValueByTime {args} {
    set signal [lindex $args 2]; set t [lindex $args end]
    if {[string match */pulse $signal]} {
        if {$t >= 5000 && $t < 5001} {return 1}
        return 0
    }
    if {[string match *clk $signal]} {return [expr {int($t/5000)%2}]}
    if {[string match */flat $signal]} {return x}
    if {[string match */signed $signal]} {
        if {[lindex $args 4] eq "Bin"} {return 11111111}
        return 255
    }
    return {10xz}
}
proc wvSearchNextBySignal {args} {
    set signal [lindex $args 4]; set t [lindex $args 6]
    if {[string match */stuck_search $signal]} {set ::cursor 123; return [list 1 $t]}
    if {[string match */slow_clk $signal]} {after 20}
    if {[string match *clk $signal]} {
        set next [expr {(int($t/5000)+1)*5000}]
        if {$next > 1000000} {return 0}
        set ::cursor $next
        return [list 1 $next]
    }
    if {[string match */pulse $signal]} {
        foreach next {5000 5001} {
            if {$next > $t} {set ::cursor $next; return [list 1 $next]}
        }
    }
    return 0
}
proc srcTraceDriver {args} {return {tb.dut fifo.sv 20}}
proc srcGetFileName {args} {return $::env(TEST_SOURCE)}
proc srcGetDefLine {args} {return 2}
proc srcSetScope {args} {return 1}
proc srcGotoLine {args} {return 1}
source [lindex $argv 0]
vwait forever
