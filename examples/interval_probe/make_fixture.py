"""Generate a tiny known waveform for live-Verdi API checks; not a simulator."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    (args.directory / 'tb.sv').write_text(
        'module tb; reg pulse; reg signed [7:0] signed_value; endmodule\n')
    (args.directory / 'wave.vcd').write_text('''$timescale 1ps $end
$scope module tb $end
$var reg 1 ! pulse $end
$var reg 8 # signed_value [7:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b00000001 #
#5000
1!
#5001
0!
b11111111 #
#6000
x!
#7000
z!
#8000
0!
#10000
b00000010 #
''')
    print(args.directory.resolve())


if __name__ == '__main__':
    main()
