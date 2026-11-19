---
name: Duke 写作工作室
description: 供中文写作者起草、复核与修订稿件的独立出版工作室。
colors:
  canvas: "#f9f8f4"
  surface: "#fffefa"
  ink: "#222126"
  muted: "#64616b"
  rule: "#dcd9d2"
  rule-dark: "#aaa7ad"
  blue: "#343bc2"
  blue-deep: "#252b96"
  lilac: "#e7e1fa"
  butter: "#f7e6a3"
typography:
  headline:
    fontFamily: "Duke Press, Noto Serif CJK SC, Songti SC, SimSun, serif"
    fontSize: "3.3rem"
    fontWeight: 900
    lineHeight: 1.16
    letterSpacing: "-0.04em"
  wordmark:
    fontFamily: "Bricolage Grotesque, PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.04em"
  body:
    fontFamily: "Instrument Sans, PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.55
  manuscript:
    fontFamily: "Noto Serif CJK SC, Songti SC, SimSun, serif"
    fontSize: "1.02rem"
    lineHeight: 1.95
rounded:
  field: "6px"
  button: "7px"
  sheet: "12px"
  role: "30px"
spacing:
  field-gap: "0.4rem"
  form-gap: "1rem"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "#ffffff"
    rounded: "{rounded.button}"
    padding: "0.59rem 1.14rem"
  button-primary-hover:
    backgroundColor: "{colors.blue-deep}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.button}"
    padding: "0.59rem 1.14rem"
  input:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.field}"
    padding: "0.65rem 0.78rem"
  site-nav:
    textColor: "{colors.muted}"
  role-active:
    backgroundColor: "#292633"
    textColor: "#ffffff"
    rounded: "{rounded.role}"
  sheet:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.sheet}"
  handbook:
    backgroundColor: "{colors.butter}"
    textColor: "#302a20"
---

# Duke 写作工作室

## Overview

**Creative North Star: "独立出版工作室"**

铅笔、圈画笔迹和校样拼贴把写作台与产品介绍连在一起。进入稿纸后，材料、正文和复核意见占据主要阅读空间。

**Key Characteristics:**

- 淡紫封面、钴蓝油墨、奶油色稿纸。
- 在作者身边留一本可随工作角色切换的手册。
- 使用本地字体和图像，在内网也能看到完整的版面。

## Colors

钴蓝用于主要动作、当前导航和键盘焦点，深蓝用于悬停。淡紫用于封面、稿件状态和总览数字带。浅黄用于角色手册，产品页的大块橙红来自校样插画。纸张色承载输入区，墨色正文与灰色次要说明形成阅读层次。产品介绍的深色模式通过变更纸张、文字与分隔线的色值保持对比。

## Typography

写作台、产品首页和总览的大标题使用本地 Duke Press 中文字形。Duke 字标和总览数字使用 Bricolage Grotesque。表单使用中文无衬线字体，完整稿件使用宋体风格的本机字体，与编辑控件区分。

**The Manuscript Rule.** 正文保留原始段落与换行，桌面阅读行宽上限为 70ch。

## Layout

共享页头与内容区在宽屏上居中，最大宽度为 1280px。写作台把角色选择放在稿纸之前，稿纸占主列，角色手册与稿件记录在右栏。720px 及以下改为单列编辑区，520px 及以下用三列按钮排出六个角色。产品介绍在 620px 及以下把标题与图版上下排列。总览中的指标带在 720px 及以下折成两列。

## Elevation & Depth

稿纸通过实色底和细线与桌面分开，手册使用书脊双线与钴蓝书签。弹窗用半透明遮罩标明焦点。

## Shapes

输入框与操作按钮使用小圆角。角色按钮两端圆润，手册左侧圆角小于右侧，形成装订边。站点标记使用微倾的钴蓝星形。

## Components

- **导航**用下划线与文字颜色标出当前页，键盘焦点使用带间距的蓝色轮廓。
- **操作按钮**以钴蓝实底标示提交或进入工作区，次要操作使用纸白色与细边框。
- **稿纸**将角色标题、输入区和正文分段，事实依据与本轮修改要求有各自的字段标签。
- **角色手册**随所选角色显示交付内容和复核边界。已选角色使用深墨色背景与白字。
- **平台总览**把指标、数值与单位排在同一条带内，流程与清单利用分隔线组织密集信息。

## Do's and Don'ts

- **Do** 用两段完整短语安排产品标题在手机上的换行。
- **Do** 保留稿件状态文字以及按钮的可见焦点。
- **Don't** 把封面拼贴延伸到草稿与复核正文背后。
- **Don't** 仅靠状态颜色区分当前角色或待复核稿件。
