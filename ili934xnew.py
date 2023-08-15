# This is an adapted version of the ILI934X driver as below.
# It works with multiple fonts and also works with the esp32 H/W SPI implementation
# Also includes a word wrap print function
# Proportional fonts are generated by Peter Hinch's Font-to-py
# MIT License; Copyright (c) 2017 Jeffrey N. Magee

# This file is part of MicroPython ILI934X driver
# Copyright (c) 2016 - 2017 Radomir Dopieralski, Mika Tuupola
#
# Licensed under the MIT license:
#   http://www.opensource.org/licenses/mit-license.php
#
# Project home:
#   https://github.com/tuupola/micropython-ili934x
# Revise by Yishang:
#   https://gitee.com/wojiaoyishang/mpython-tft-ili934x-driver

import time
import ustruct
import framebuf

from mpython import *

_RDDSDR = const(0x0f) # Read Display Self-Diagnostic Result
_SLPOUT = const(0x11) # Sleep Out
_GAMSET = const(0x26) # Gamma Set
_DISPOFF = const(0x28) # Display Off
_DISPON = const(0x29) # Display On
_CASET = const(0x2a) # Column Address Set
_PASET = const(0x2b) # Page Address Set
_RAMWR = const(0x2c) # Memory Write
_RAMRD = const(0x2e) # Memory Read
_MADCTL = const(0x36) # Memory Access Control
_VSCRSADD = const(0x37) # Vertical Scrolling Start Address
_PIXSET = const(0x3a) # Pixel Format Set
_PWCTRLA = const(0xcb) # Power Control A
_PWCRTLB = const(0xcf) # Power Control B
_DTCTRLA = const(0xe8) # Driver Timing Control A
_DTCTRLB = const(0xea) # Driver Timing Control B
_PWRONCTRL = const(0xed) # Power on Sequence Control
_PRCTRL = const(0xf7) # Pump Ratio Control
_PWCTRL1 = const(0xc0) # Power Control 1
_PWCTRL2 = const(0xc1) # Power Control 2
_VMCTRL1 = const(0xc5) # VCOM Control 1
_VMCTRL2 = const(0xc7) # VCOM Control 2
_FRMCTR1 = const(0xb1) # Frame Rate Control 1
_DISCTRL = const(0xb6) # Display Function Control
_ENA3G = const(0xf2) # Enable 3G
_PGAMCTRL = const(0xe0) # Positive Gamma Control
_NGAMCTRL = const(0xe1) # Negative Gamma Control

_CHUNK = const(1024) #maximum number of pixels per spi write

def color565(r, g, b):
    return (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3

class ILI9341:

    def __init__(self, spi, cs=Pin(Pin.P16), dc=Pin(Pin.P14), rst=Pin(Pin.P15), led=Pin(Pin.P8, Pin.OUT), w=320, h=240, r=0):
        self.spi = spi
        self.cs = cs
        self.dc = dc
        self.rst = rst
        self.led = led
        self._init_width = w
        self._init_height = h
        self.width = w
        self.height = h
        self.rotation = r
        self.cs.init(self.cs.OUT, value=1)
        self.dc.init(self.dc.OUT, value=0)
        self.rst.init(self.rst.OUT, value=0)
        self.reset()
        self.init()
        self._scroll = 0
        self._buf = bytearray(_CHUNK * 2)
        self._colormap = bytearray(b'\x00\x00\xFF\xFF') #default white foregraound, black background
        self._x = 0
        self._y = 0
        self.scrolling = False
    
    def deinit(self):
        self.spi.deinit()
    
    def poweron(self):
        self.led.value(1)
        
    def poweroff(self):
        self.led.value(0)
    
    def set_color(self,fg,bg):
        self._colormap[0] = bg>>8
        self._colormap[1] = bg & 255
        self._colormap[2] = fg>>8
        self._colormap[3] = fg & 255

    def set_pos(self,x,y):
        self._x = x
        self._y = y

    def reset_scroll(self):
        self.scrolling = False
        self._scroll = 0
        self.scroll(0)

    def init(self):
        for command, data in (
            (_RDDSDR, b"\x03\x80\x02"),
            (_PWCRTLB, b"\x00\xc1\x30"),
            (_PWRONCTRL, b"\x64\x03\x12\x81"),
            (_DTCTRLA, b"\x85\x00\x78"),
            (_PWCTRLA, b"\x39\x2c\x00\x34\x02"),
            (_PRCTRL, b"\x20"),
            (_DTCTRLB, b"\x00\x00"),
            (_PWCTRL1, b"\x23"),
            (_PWCTRL2, b"\x10"),
            (_VMCTRL1, b"\x3e\x28"),
            (_VMCTRL2, b"\x86")):
            self._write(command, data)

        if self.rotation == 0:                  # 0 deg
            self._write(_MADCTL, b"\x48")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 1:                # 90 deg
            self._write(_MADCTL, b"\x28")
            self.width = self._init_width
            self.height = self._init_height
        elif self.rotation == 2:                # 180 deg
            self._write(_MADCTL, b"\x88")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 3:                # 270 deg
            self._write(_MADCTL, b"\xE8")
            self.width = self._init_width
            self.height = self._init_height
        elif self.rotation == 4:                # Mirrored + 0 deg
            self._write(_MADCTL, b"\xC8")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 5:                # Mirrored + 90 deg
            self._write(_MADCTL, b"\x68")
            self.width = self._init_width
            self.height = self._init_height
        elif self.rotation == 6:                # Mirrored + 180 deg
            self._write(_MADCTL, b"\x08")
            self.width = self._init_height
            self.height = self._init_width
        elif self.rotation == 7:                # Mirrored + 270 deg
            self._write(_MADCTL, b"\xA8")
            self.width = self._init_width
            self.height = self._init_height
        else:
            self._write(_MADCTL, b"\x08")

        for command, data in (
            (_PIXSET, b"\x55"),
            (_FRMCTR1, b"\x00\x18"),
            (_DISCTRL, b"\x08\x82\x27"),
            (_ENA3G, b"\x00"),
            (_GAMSET, b"\x01"),
            (_PGAMCTRL, b"\x0f\x31\x2b\x0c\x0e\x08\x4e\xf1\x37\x07\x10\x03\x0e\x09\x00"),
            (_NGAMCTRL, b"\x00\x0e\x14\x03\x11\x07\x31\xc1\x48\x08\x0f\x0c\x31\x36\x0f")):
            self._write(command, data)
        self._write(_SLPOUT)
        time.sleep_ms(120)
        self._write(_DISPON)

    def reset(self):
        self.rst(0)
        time.sleep_ms(50)
        self.rst(1)
        time.sleep_ms(50)

    def _write(self, command, data=None):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([command]))
        self.cs(1)
        if data is not None:
            self._data(data)

    def _data(self, data):
        self.dc(1)
        self.cs(0)
        self.spi.write(data)
        self.cs(1)

    def _writeblock(self, x0, y0, x1, y1, data=None):
        self._write(_CASET, ustruct.pack(">HH", x0, x1))
        self._write(_PASET, ustruct.pack(">HH", y0, y1))
        self._write(_RAMWR, data)

    def _readblock(self, x0, y0, x1, y1, data=None):
        self._write(_CASET, ustruct.pack(">HH", x0, x1))
        self._write(_PASET, ustruct.pack(">HH", y0, y1))
        if data is None:
            return self._read(_RAMRD, (x1 - x0 + 1) * (y1 - y0 + 1) * 3)

    def _read(self, command, count):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([command]))
        data = self.spi.read(count)
        self.cs(1)
        return data

    def pixel(self, x, y, color=None):
        if color is None:
            r, b, g = self._readblock(x, y, x, y)
            return color565(r, g, b)
        if not 0 <= x < self.width or not 0 <= y < self.height:
            return
        self._writeblock(x, y, x, y, ustruct.pack(">H", color))

    def fill_rectangle(self, x, y, w, h, color=None):
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        w = min(self.width - x, max(1, w))
        h = min(self.height - y, max(1, h))
        if color:
            color = ustruct.pack(">H", color)
        else:
            color = self._colormap[0:2] #background
        for i in range(_CHUNK):
            self._buf[2*i]=color[0]; self._buf[2*i+1]=color[1]
        chunks, rest = divmod(w * h, _CHUNK)
        self._writeblock(x, y, x + w - 1, y + h - 1, None)
        if chunks:
            for count in range(chunks):
                self._data(self._buf)
        if rest != 0:
            mv = memoryview(self._buf)
            self._data(mv[:rest*2])

    def fill(self, c=None):
        self.fill_rectangle(0, 0, self.width, self.height, c)

    def blit(self, bitbuff, x, y, w, h, rgb565=False):
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        w = min(self.width - x, max(1, w))
        h = min(self.height - y, max(1, h))
        chunks, rest = divmod(w * h, _CHUNK)
        self._writeblock(x, y, x + w - 1, y + h - 1, None)
        written = 0
        for iy in range(h):
            for ix in range(w):
                index = ix+iy*w - written
                if index >=_CHUNK:
                    self._data(self._buf)
                    written += _CHUNK
                    index   -= _CHUNK
                c = bitbuff.pixel(ix,iy)
                if rgb565:
                    if c is not None:
                        self._buf[index*2] = c >> 8
                        self._buf[index*2+1] = c & 0xFF
                else:
                    self._buf[index*2] = self._colormap[c*2]
                    self._buf[index*2+1] = self._colormap[c*2+1]
        rest = w*h - written
        if rest != 0:
            mv = memoryview(self._buf)
            self._data(mv[:rest*2])

    def scroll(self, dy):
        self._scroll = (self._scroll + dy) % self.height
        self._write(_VSCRSADD, ustruct.pack(">H", self._scroll))

    def DispChar_font(self, font, s, x, y):
        str_w  = font.get_width(s)
        div, rem = divmod(font.height(),8)
        nbytes = div+1 if rem else div
        buf = bytearray(str_w * nbytes)
        pos = 0
        for ch in s:
            glyph, char_w = font.get_ch(ch)
            for row in range(nbytes):
                index = row*str_w + pos
                for i in range(char_w):
                    buf[index+i] = glyph[nbytes*i+row]
            pos += char_w
        fb = framebuf.FrameBuffer(buf, str_w, font.height(), framebuf.MONO_VLSB)
        self.blit(fb,x,y,str_w,font.height())
        return x+str_w

    def DispChar(self, s, x, y, color=65535, buffer_char_line=1, buffer_width=None):
        if buffer_width is None:
            buffer_width = self.width

        # Calculate buffer size based on buffer_char_line and buffer_width
        buffer_height = oled.f.height * buffer_char_line
        buf = bytearray(buffer_width * buffer_height * 2)  # 2 bytes per pixel for RGB565
        fb = framebuf.FrameBuffer(buf, buffer_width, buffer_height, framebuf.RGB565)

        # Draw each character onto the buffer, line by line
        cur_x = 0
        cur_y = 0
        for c in s:
            data = oled.f.GetCharacterData(c)
            if data:
                width, bytes_per_line = ustruct.unpack('HH', data[:4])
                if c == " ":
                    width += 3
                if cur_x + width > buffer_width:  # Check if we need to wrap to the next line
                    cur_x = 0
                    cur_y += oled.f.height
                    
                    # Check if we've exceeded the buffer height
                    if cur_y + oled.f.height > buffer_height:
                        self.blit(fb, x, y, buffer_width, cur_y, rgb565=True)
                        y += buffer_height
                        fb.fill(0)  # Clear the framebuffer
                        cur_y = 0

                for h in range(0, oled.f.height):
                    w = 0
                    i = 0
                    while w < width:
                        mask = data[4 + h * bytes_per_line + i]
                        if (width - w) >= 8:
                            n = 8
                        else:
                            n = width - w
                        for p in range(0, n):
                            if (mask & 0x80) != 0:
                                fb.pixel(cur_x + w + p, cur_y + h, color)
                            mask = mask << 1
                        w += 8
                        i += 1
                cur_x += width

        # Blit any remaining content in the buffer to the screen
        self.blit(fb, x, y, buffer_width, cur_y + oled.f.height, rgb565=True)
                
    def DispBmp(self, bmpr_reader, x, y, framebuf_line=1):
        
        width = bmpr_reader.get_width()
        height = bmpr_reader.get_height()
        
        line_count = 0
        
        buffer = bytearray(width * framebuf_line * 2)
        fb = framebuf.FrameBuffer(buffer, width, framebuf_line, framebuf.RGB565)
        
        for row_i in range(height):
            
            for col_i, color in enumerate(bmpr_reader.get_row_yield(row_i)):
                fb.pixel(col_i, line_count, color565(color.red, color.green, color.blue))
            
            line_count += 1
            
            if line_count >= framebuf_line:
                self.blit(fb, x, y + row_i - framebuf_line, width, framebuf_line, True)
                fb.fill(0)
                line_count = 0
                
        self.blit(fb, x, y + row_i - line_count, width, framebuf_line, True)
        del buffer, fb
            
            



