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
proc wvGetScope {args} {return {/tb/dut}}
proc wvGetSignalsByScope {args} {
    set names {ptr[3:0] full}
    for {set i 0} {$i < 16} {incr i} {lappend names s$i}
    if {[info exists ::env(TEST_LITERAL_SIGNAL)]} {lappend names $::env(TEST_LITERAL_SIGNAL)}
    return $names
}
proc wvGetSigValueByTime {args} {return {10xz}}
proc srcTraceDriver {args} {return {tb.dut fifo.sv 20}}
proc srcGetFileName {args} {return $::env(TEST_SOURCE)}
proc srcGetDefLine {args} {return 2}
proc srcSetScope {args} {return 1}
proc srcGotoLine {args} {return 1}
source [lindex $argv 0]
vwait forever
