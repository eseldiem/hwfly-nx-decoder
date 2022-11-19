## hwfly-nx SPI commands decoder
##
## Copyright (c) 2022 eseldiem <none.of@your.busine.ss>
##
## License: GPLv2.

'''
This decoder stacks on top of the 'spi' PD and decodes hwfly-nx
SPI comms protocol.

In order to work, you MUST enable frame decoder in the SPI options, and
supply all 4 lines (clk, miso, mosi, cs).

It supports whatever github.com/hwfly-nx/firmware supports as of 2022-11-16.
'''

from .pd import Decoder
