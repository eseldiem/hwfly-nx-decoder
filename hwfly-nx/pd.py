## hwfly-nx SPI commands decoder
##
## Copyright (c) 2022 eseldiem <none.of@your.busine.ss>
##
## License: GPLv2.

#import random
import sigrokdecode as srd

class ChannelError(Exception):
    pass

class Decoder(srd.Decoder):
  api_version = 3
  id = 'hwfly-nx'
  name = 'hwfly-nx SPI'
  longname = 'hwfly-nx SPI'
  desc = 'hwfly-nx SPI communication between MCU and FPGA.'
  license = 'gplv2'
  inputs = ['spi']
  outputs = []
  tags = ['hwfly', 'modchip']

  ann_read = 0
  ann_write = 1
  ann_payload = 2
  ann_response = 3
  ann_garbage = 4
  annotations = (
    ('Read', 'Read request'),
    ('Write', 'Write request'),
    ('Payload', 'Payload sent'),
    ('Response', 'Response from chip'),
    ('Garbage', 'Garbage (unknown)'),
  )
  annotation_rows = (
    ('Commands', 'Commands', (ann_read, ann_write, ann_payload, ann_response, ann_garbage)),
  )
  options = (
    {'id': 'merge_flag_reads', 'desc': 'Merge flag read and response into single annotation', 'default': 'no', 'values': ('yes', 'no')},
  )

  def __init__(self):
    self.reset()

  def reset(self):
    self.requirements_met = True

  def start(self):
    self.out_ann = self.register(srd.OUTPUT_ANN)
    pass

  def command_24_6(self, mosi, miso):
    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))
        
    cmd2 = mosi[2].val
    if cmd2 == 0x00:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Stop glitching']])
    elif cmd2 == 0x01:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Enter cmd mode 2/2']])
    elif cmd2 == 0x03:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Post send']])
    elif cmd2 == 0x04:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Enter cmd mode 1/2']])
    elif cmd2 == 0x05:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Post recv']])
    elif cmd2 == 0x10:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Start glitching']])
    elif cmd2 == 0x40:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Reset device (cmd stuck)']])
    elif cmd2 == 0x80:
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Reset device (normal)']])
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized 0x24 0x6 command']])

  def command_24(self, mosi, miso):
    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))
        
    cmd1 = mosi[1].val
    if cmd1 == 0x1:
      if txn_length >= 4:
        self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_write, ['Set glitch offset']])
        self.put(mosi[2].ss, mosi[3].es, self.out_ann, [self.ann_payload, ['{:d}'.format((mosi[3].val << 8) + mosi[2].val)]])
      else:
        self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Invalid set_glitch_offset (too short?)']])
    elif cmd1 == 0x2:
      self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_write, ['Set glitch width']])
      self.put(mosi[2].ss, mosi[2].es, self.out_ann, [self.ann_payload, ['{:d}'.format(mosi[2].val)]])
    elif cmd1 == 0x3:
      self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_write, ['Set glitch timeout']])
      self.put(mosi[2].ss, mosi[2].es, self.out_ann, [self.ann_payload, ['{:d}'.format(mosi[2].val)]])
    elif cmd1 == 0x5:
      self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_write, ['Select active buffer']])
      b = mosi[2].val
      if b == 0:
        buf = 'CMD (traffic on cmd line)'
      elif b == 1:
        buf = 'DATA (data host->device)'
      elif b == 2:
        buf = 'RESP (data device->host)'
      else:
        buf = 'unknown {:d}'.format(b)
      self.put(mosi[2].ss, mosi[2].es, self.out_ann, [self.ann_payload, [buf]])
    elif cmd1 == 0x6:
      self.command_24_6(mosi, miso)
    elif cmd1 == 0x8:
      self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_write, ['Set subcycle delay']])
      self.put(mosi[2].ss, mosi[2].es, self.out_ann, [self.ann_payload, ['{:d}'.format(mosi[2].val)]])
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized 0x24 command']])

  def command_26(self, mosi, miso):
    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))
        
    cmd1 = mosi[1].val
    if cmd1 == 0xA:
      if self.options['merge_flag_reads'] == 'no':
        self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_read, ['Read glitch timer']])
        self.put(miso[2].ss, miso[2].es, self.out_ann, [self.ann_response, ['{:d}'.format(miso[2].val)]])
      else:
        self.put(mosi[0].ss, miso[2].es, self.out_ann, [self.ann_read, ['Read glitch timer: {:d}'.format(miso[2].val)]])
    elif cmd1 == 0xB:
      b = miso[2].val
      out = []
      if b & 0x01:
        out.append('BUSY_SENDING')
      if b & 0x02:
        out.append('GLITCH_SUCCESS')
      if b & 0x04:
        out.append('GLITCH_TIMEOUT')
      if b & 0x08:
        out.append('UNKNOWN1')
      if b & 0x10:
        out.append('LOADER_DATA_RCVD')
      if b & 0x20:
        out.append('UNKNOWN2')
      if b & 0x40:
        out.append('GLITCH_DT_CAPTURED')
      if b & 0x80:
        out.append('UNKNOWN2')
      if len(out) == 0:
        out.append('NONE')
      if self.options['merge_flag_reads'] == 'no':
        self.put(mosi[0].ss, mosi[1].es, self.out_ann, [self.ann_read, ['Read eMMC flags']])
        self.put(miso[2].ss, miso[2].es, self.out_ann, [self.ann_response, [', '.join(out)]])
      else:
        self.put(mosi[0].ss, miso[2].es, self.out_ann, [self.ann_read, ['Read eMMC flags: ' + ', '.join(out)]])
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized 0x26 command']])

  def command(self, mosi, miso):
    if len(mosi) == 0 and len(miso) == 0:
      return

    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))

    cmd0 = mosi[0].val
    if cmd0 == 0x24:
      if txn_length >= 3:
        self.command_24(mosi, miso)
      else:
        self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized (too short?)']])
    elif cmd0 == 0x26:
      if txn_length >= 3:
        self.command_26(mosi, miso)
      else:
        self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized (too short?)']])
    elif cmd0 == 0x54:
      self.put(miso[0].ss, miso[0].es, self.out_ann, [self.ann_write, ['Do eMMC command']])
    elif cmd0 == 0xBA:
      self.put(mosi[0].ss, mosi[0].es, self.out_ann, [self.ann_read, ['Read buffer']])
      self.put(miso[1].ss, miso[-1].es, self.out_ann, [self.ann_response, [' '.join(['{:02X}'.format(m.val) for m in miso[1:]])]])
    elif cmd0 == 0xBC:
      self.put(mosi[0].ss, mosi[0].es, self.out_ann, [self.ann_read, ['Write buffer']])
      self.put(mosi[1].ss, mosi[-1].es, self.out_ann, [self.ann_response, [' '.join(['{:02X}'.format(m.val) for m in mosi[1:]])]])
    elif cmd0 == 0xEE:
      self.put(mosi[0].ss, mosi[0].es, self.out_ann, [self.ann_read, ['Read FPGA id']])
      if txn_length == 5:
        self.put(miso[1].ss, miso[4].es, self.out_ann, [self.ann_response, ['{:c}{:c}{:c}{:c}'.format(miso[1].val, miso[2].val, miso[3].val, miso[4].val)]])
      else:
        self.put(miso[1].ss, miso[-1].es, self.out_ann, [self.ann_response, [' '.join(['{:02X}'.format(m.val) for m in miso[1:]])]])
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized command']])

  def decode(self, ss, es, data):
    if not self.requirements_met:
      return

    ptype, data1, data2 = data

    if ptype == 'TRANSFER':
      self.command(data1, data2)
    elif ptype == 'CS-CHANGE':
      if data1 is None and data2 is None:
        self.requirements_met = False
        raise ChannelError('CS# pin required.')
    elif ptype == 'DATA':
      if data1 is None and data2 is None:
        self.requirements_met = False
        raise ChannelError('MISO and MOSI pins required.')
