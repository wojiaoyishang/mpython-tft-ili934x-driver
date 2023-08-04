# mpython 掌控板 ili934x tft 屏幕驱动

#### 其它项目

[mpython-oled屏幕显示图片](https://gitee.com/wojiaoyishang/new-mpython-bin-to-picture)

[mpython-操作系统](https://gitee.com/wojiaoyishang/TaoLiSystem)

#### 介绍
为掌控板定制的 mpython ili934x tft 屏幕驱动，代码逻辑遵循 mpython 的 oled 屏。

驱动源码参考至 [https://github.com/jeffmer/micropython-ili9341](https://github.com/jeffmer/micropython-ili9341) 。并依照 [mpython 掌控板文档](https://mpython.readthedocs.io/zh/master/tutorials/basics/oled.html) 修改了源码，支持调用掌控板自带的字体，也允许使用自定义的字体。

#### 使用说明

### 接入 TFT 屏幕

掌控板基于 esp32 开发板开发。查询资料显示 esp32 有两个 SPI（串行外设接口），分别如下所示：

+ HSPI（Hardware SPI）接口：

    - MOSI (Master Out Slave In) 默认引脚是GPIO13
    - MISO (Master In Slave Out) 默认引脚是GPIO12
    - SCK (Serial Clock) 默认引脚是GPIO14
    - CS (Chip Select) 默认引脚可以任意选择（通常选择 GPIO15）

+ VSPI（VSP Interface）接口：

    - MOSI 默认引脚是GPIO23
    - MISO 默认引脚是GPIO19
    - SCK 默认引脚是GPIO18
    - CS 默认引脚可以任意选择（通常选择 GPIO5）

因为掌控板重新定义了引脚，请查看官方给出的[引脚参考图](https://mpython.readthedocs.io/zh/master/_images/mPython%E6%8E%8C%E6%8E%A7%E6%9D%BF_pin_define.jpg)

这里我们选择VSPI接口连接TFT屏，TFT屏幕引脚与掌控板对应如下：

|TFT屏幕引脚|掌控板引脚|
|:----:|:----:|
|VCC|3V3或VCC|
|GND|GND|
|CS|P16|
|RESET|P15|
|DC|P14|
|SDI(MOSI)|P20(SDA)|
|SCK|P13|
|LED|P8|
|SDO(MISO)|P19(SCL)|

连接好后，下载仓库里面对应的代码文件 `ili934xnew.py` 为模块，使用下面的代码激活TFT屏幕。

```python
from ili934xnew import ILI9341, color565
tft = ILI9341()
```

实际上，原代码是这样的：

```python
spi = SPI(2, baudrate=20000000, miso=Pin(Pin.P19), mosi=Pin(Pin.P20), sck=Pin(Pin.P13))
tft = ILI9341(spi, cs=Pin(Pin.P16), dc=Pin(Pin.P14), rst=Pin(Pin.P15), led=Pin(Pin.P12), w=320, h=240, r=0)
# 注：led是用来电亮TFT屏幕的，w是屏幕的宽度，h是屏幕的高度，r是旋转角度，r=90就是选择90度。
```

如果你想采用其它的引脚来与TFT屏幕交互，你可以在原代码的基础上稍作修改。

### 显示文字

显示掌控板自带的字库可以使用如下代码：

```python
from ili934xnew import ILI9341, color565
tft = ILI9341()
tft.poweron()  # 默认不开启屏幕，需要手动打开
tft.fill(0)
tft.DispChar("测试，皮卡丘皮卡丘皮卡丘！！！\nHere some interesting for you.\n" + "长文本" * 100, 0, 0, color565(255, 255, 255), auto_return=True)
```

***因为掌控板运存比较小，所以对于屏幕比较大的TFT屏幕没有全屏幕缓存区操作，所以此驱动没有 `tft.show()` 方法。DispChar()方法是单字刷新。***

`fill()` 与 `DispChar()` 参考 [https://mpython.readthedocs.io/zh/master/library/mPython/mpython.html?mpython.oled.DispChar#rgb](https://mpython.readthedocs.io/zh/master/library/mPython/mpython.html?mpython.oled.DispChar#rgb)。

**此模块的所有函数，均模仿官方的oled屏幕集成的函数，不同函数使用会说明。**

![输入图片说明](https://foruda.gitee.com/images/1691145621865141314/e3aa6b53_5210553.png "屏幕截图")

同时含有也有方法 `DispChar_font()` ，使用方式同 mpython 的 oled。

### 绘制图形

由于ILI9341驱动并不是以framebuf为父类，随意绘制图行需要[framebuf](https://mpython.readthedocs.io/zh/master/library/micropython/framebuf.html)作为中介。比如我可以这样画一个圆和线：

```
import framebuf
buffer = bytearray(50 * 50 * 2)  # 假设我要绘制 50 * 50 的图形，还要再乘2是因为RGB565每个颜色占两个字节
fbuf = framebuf.FrameBuffer(buffer, 50, 50, framebuf.RGB565)  # 第一个 50 为宽，第二个 50 为高，模式为 rgb565
fbuf.fill_circle(25, 25, 24, color565(255, 255, 0))  # 以点 (25, 25) 为圆心（以framebuf为基准），画一个半径为 24 的黄圆
fbuf.hline(0, 25, 50, color565(255, 0, 0))  # 在 (0, 25) 为点画长为 25 的红线
tft.blit(fbuf, 20, 40, 50, 50, True)  # 把framebuf贴在屏幕 (20, 40) 的位置，最后一个参数表示是否是 rgb565 模式，默认为不是。
```

![输入图片说明](https://foruda.gitee.com/images/1691151341282674316/5155c240_5210553.png "屏幕截图")

### 绘制图片

绘制图片***只支持24位的bmp图片***，准备好图片后，采用开源项目的 [bmp_file_reader](https://github.com/ExcaliburZero/bmp_file_reader) 读取图片。

```
import framebuf
import bmp_file_reader as bmpr
from ili934xnew import ILI9341, color565
tft = ILI9341()
tft.poweron()
tft.fill(0)
with open("1.bmp", "rb") as file_handle:
    tft.DispBmp(bmpr.BMPFileReader(file_handle), 0, 0, 5)  # 第二个参数是x坐标，第三个参数是y坐标，第四个参数是缓存的行数，默认一行一行刷新。
```

![输入图片说明](https://foruda.gitee.com/images/1691152883284359035/8515c01d_5210553.png "屏幕截图")

