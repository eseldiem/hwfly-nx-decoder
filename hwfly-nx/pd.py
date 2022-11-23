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
  ann_garbage = 2
  annotations = (
    ('Read', 'Read request'),
    ('Write', 'Write request'),
    ('Garbage', 'Garbage (unknown)'),
  )
  annotation_rows = (
    ('Commands', 'Commands', (ann_read, ann_write, ann_garbage)),
  )
  options = (
    {'id': 'merge_same_flag_annots', 'desc': 'Merge same flag annotations into a single annotation', 'default': 'yes', 'values': ('yes', 'no')},
  )

  def __init__(self):
    self.reset()

  def reset(self):
    self.requirements_met = True
    self.current_flags = None
    self.current_timer = None

  def start(self):
    self.out_ann = self.register(srd.OUTPUT_ANN)

  def command_24_6(self, mosi, miso):
    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
 
    cmd2 = mosi[2].val
    out = lambda msg: self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, msg])
    if cmd2 == 0x00:
      out(['Stop glitching', 'G:Stop', 'G[]'])
    elif cmd2 == 0x01:
      out(['Enter cmd mode 2/2', 'CmdMode 2/2', 'CM:2/2'])
    elif cmd2 == 0x03:
      out(['Post send', 'Send|'])
    elif cmd2 == 0x04:
      out(['Enter cmd mode 1/2', 'CmdMode 1/2', 'CM:1/2'])
    elif cmd2 == 0x05:
      out(['Post recv', 'Rcv|'])
    elif cmd2 == 0x10:
      out(['Start glitching', 'G:Start', 'G|>'])
    elif cmd2 == 0x40:
      out(['Reset device (cmd stuck)', 'Reset+CmdStuck', 'Rst+CS'])
    elif cmd2 == 0x80:
      out(['Reset device (normal)', 'Reset', 'Rst'])
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized 0x24 0x6 command', '??? 24 06']])

  def command_24(self, mosi, miso):
    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))
        
    cmd1 = mosi[1].val
    if cmd1 == 0x1:
      if txn_length >= 4:
        o = '{:d}'.format((mosi[3].val << 8) + mosi[2].val)
        self.put(mosi[0].ss, mosi[3].es, self.out_ann, [self.ann_write, ['Set glitch offset: ' + o, 'GO:' + o]])
      else:
        self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Invalid set_glitch_offset (too short?)', 'GO:?']])
    elif cmd1 == 0x2:
      o = '{:d}'.format(mosi[2].val)
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Set glitch width: ' + o, 'GW:' + o]])
    elif cmd1 == 0x3:
      o = '{:d}'.format(mosi[2].val)
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Set glitch timeout: ' + o, 'GT:' + o]])
    elif cmd1 == 0x5:
      b = mosi[2].val
      if b == 0:
        buf = 'CMD (traffic on cmd line)'
        buf_short = 'cmd'
      elif b == 1:
        buf = 'DATA (data host->device)'
        buf_short = 'dta'
      elif b == 2:
        buf = 'RESP (data device->host)'
        buf_short = 'rsp'
      else:
        buf = 'unknown {:d}'.format(b)
        buf_short = '???'
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Select active buffer: ' + buf, 'SB:' + buf_short]])
    elif cmd1 == 0x6:
      self.command_24_6(mosi, miso)
    elif cmd1 == 0x8:
      o = '{:d}'.format(mosi[2].val)
      self.put(mosi[0].ss, mosi[2].es, self.out_ann, [self.ann_write, ['Set subcycle delay: ' + o, 'SD:' + o]])
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized 0x24 command', '??? 24']])

  def maybe_close_26(self):
    if self.current_flags or self.current_timer:
      ss = None
      es = None
      out = []
      out_short = []
      if self.current_flags:
        if ss:
          ss = min(self.current_flags[0], ss)
        else:
          ss = self.current_flags[0]
        if es:
          es = max(self.current_flags[1], es)
        else:
          es = self.current_flags[1]
        out.append('Flags: ' + self.current_flags[2])
        out_short.append('F:' + self.current_flags[3])
      if self.current_timer:
        if ss:
          ss = min(self.current_timer[0], ss)
        else:
          ss = self.current_timer[0]
        if es:
          es = max(self.current_timer[1], es)
        else:
          es = self.current_timer[1]
        out.append('Glitch timer: ' + self.current_timer[2])
        out_short.append('T:' + self.current_timer[2])
      self.put(ss, es, self.out_ann, [self.ann_read, [', '.join(out), ','.join(out_short)]])
      self.current_flags = None
      self.current_timer = None
    else:
      return
    

  def command_26(self, mosi, miso):
    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))
        
    cmd1 = mosi[1].val
    if cmd1 == 0xA:
      d = '{:d}'.format(miso[2].val)
      if self.options['merge_same_flag_annots'] == 'no':
        self.current_timer = [mosi[0].ss, miso[2].es, d]
        self.maybe_close_26()
      else:
        if self.current_timer:
          if self.current_timer[2] == d:
            self.current_timer[1] = miso[2].es
          else:
            self.maybe_close_26()
            self.current_timer = [mosi[0].ss, miso[2].es, d]
        else:
          self.current_timer = [mosi[0].ss, miso[2].es, d]
    elif cmd1 == 0xB:
      b = miso[2].val
      out = []
      out_short = []
      if b & 0x01:
        out.append('BUSY_SENDING')
        out_short.append('bs')
      if b & 0x02:
        out.append('GLITCH_SUCCESS')
        out_short.append('g+')
      if b & 0x04:
        out.append('GLITCH_TIMEOUT')
        out_short.append('g-')
      if b & 0x08:
        out.append('UNKNOWN1')
        out_short.append('u1')
      if b & 0x10:
        out.append('LOADER_DATA_RCVD')
        out_short.append('ld')
      if b & 0x20:
        out.append('UNKNOWN2')
        out_short.append('u2')
      if b & 0x40:
        out.append('GLITCH_DT_CAPTURED')
        out_short.append('dc')
      if b & 0x80:
        out.append('UNKNOWN3')
        out_short.append('u3')
      if len(out) == 0:
        out.append('NONE')
        out_short.append('_')
      d = ', '.join(out)
      ds = ','.join(out_short)
      if self.options['merge_same_flag_annots'] == 'no':
        self.current_flags = [mosi[0].ss, miso[2].es, d, ds]
        self.maybe_close_26()
      else:
        if self.current_flags:
          if self.current_flags[2] == d:
            self.current_flags[1] = miso[2].es
          else:
            self.maybe_close_26()
            self.current_flags = [mosi[0].ss, miso[2].es, d, ds]
        else:
          self.current_flags = [mosi[0].ss, miso[2].es, d, ds]
    else:
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized 0x26 command', '??? 26']])

  def command(self, mosi, miso):
    if len(mosi) == 0 and len(miso) == 0:
      return

    start_sample = min(miso[0].ss, mosi[0].ss)
    end_sample = max(mosi[-1].es, miso[-1].es)
    txn_length = max(len(mosi), len(miso))

    cmd0 = mosi[0].val
    if cmd0 == 0x24:
      self.maybe_close_26()
      if txn_length >= 3:
        self.command_24(mosi, miso)
      else:
        self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized (too short?)', '???']])
    elif cmd0 == 0x26:
      if txn_length >= 3:
        self.command_26(mosi, miso)
      else:
        self.maybe_close_26()
        self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized (too short?)', '???']])
    elif cmd0 == 0x54:
      self.maybe_close_26()
      self.put(miso[0].ss, miso[0].es, self.out_ann, [self.ann_write, ['Do eMMC command', 'MMC|>']])
    elif cmd0 == 0xBA:
      self.maybe_close_26()
      o = ' '.join(['{:02X}'.format(m.val) for m in miso[1:]])
      self.put(miso[0].ss, miso[-1].es, self.out_ann, [self.ann_read, ['Read buffer: ' + o, 'RdBuf']])
    elif cmd0 == 0xBC:
      self.maybe_close_26()
      o = ' '.join(['{:02X}'.format(m.val) for m in mosi[1:]])
      self.put(mosi[0].ss, mosi[-1].es, self.out_ann, [self.ann_write, ['Write buffer: ' + o, 'WrBuf']])
    elif cmd0 == 0xEE:
      self.maybe_close_26()
      if txn_length == 5:
        o = '{:c}{:c}{:c}{:c}'.format(miso[1].val, miso[2].val, miso[3].val, miso[4].val)
      else:
        o = ' '.join(['{:02X}'.format(m.val) for m in miso[1:]])
      self.put(miso[0].ss, miso[4].es, self.out_ann, [self.ann_read, ['FPGA Id: ' + o, 'ID:' + o, 'Id']])
    else:
      self.maybe_close_26()
      self.put(start_sample, end_sample, self.out_ann, [self.ann_garbage, ['Unrecognized command', '???']])

  def end(self):
    self.maybe_close_26()

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
