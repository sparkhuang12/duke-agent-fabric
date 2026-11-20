---
name: Duke 写作工作室
description: 用青年杂志的摄影封面和撞色栏目组织中文写作、复核与修订。
colors:
  canvas: "#fffaf2"
  surface: "#fffefa"
  ink: "#1c191e"
  muted: "#605a60"
  rule: "#ded6ce"
  rule-dark: "#a49b98"
  blue: "#302bb9"
  blue-deep: "#272392"
  sky: "#c1e8ff"
  lime: "#e8fa53"
  pink: "#ffaaca"
typography:
  headline:
    fontFamily: "Duke Magazine, Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "clamp(2.5rem, 4.6vw, 4.45rem)"
    fontWeight: 900
    lineHeight: 1.13
    letterSpacing: "-0.04em"
  wordmark:
    fontFamily: "Bricolage Grotesque, PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif"
    fontSize: "2.25rem"
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
  button: "4px"
  square: "0px"
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
    backgroundColor: "{colors.lime}"
    textColor: "{colors.ink}"
    rounded: "{rounded.square}"
  sheet:
    backgroundColor: "{colors.surface}"
  handbook:
    backgroundColor: "{colors.sky}"
    textColor: "#192d39"
    rounded: "{rounded.square}"
  cover-action:
    backgroundColor: "{colors.ink}"
    textColor: "#ffffff"
    rounded: "{rounded.button}"
  metric-strip:
    rounded: "{rounded.square}"
---

# Duke 写作工作室

## Overview

**Creative North Star: "青年杂志编辑部"**

写作台以粉色标题栏搭配编辑桌面摄影，产品首页以荧光黄绿配人物封面摄影。读者进入编辑区后，稿纸、材料和复核意见占据主要阅读空间。

**Key Characteristics:**

- 大幅摄影与中文粗黑标题并置，封面文字落在纯色色块上。
- 荧光黄绿标出当前角色，天蓝栏保留交付内容与复核边界。
- 摄影和标题字体随应用加载，内网也能看到完整的版面。

## Colors

蓝紫用于提交动作、当前导航与键盘焦点，深蓝用于悬停。荧光黄绿、粉红、天蓝和墨黑在平台总览中分隔四项指标，数值和单位写在各自色块内。正文使用近白底、墨色文字，辅助说明使用灰色。产品介绍的深色模式调节文字、背景和分隔线，同时保留封面的亮色。

## Typography

写作台、产品页和平台总览的大标题使用本地 Duke Magazine 粗黑体。产品标题随视口缩放，字号上限为 6rem，由两段完整中文短语组成，第二段下方有略微倾斜的粉色底。Duke 字标和总览大数字使用 Bricolage Grotesque。表单使用无衬线字体，完整稿件使用宋体风格的阅读字体。

**The Manuscript Rule.** 正文保留原始段落与换行，桌面阅读行宽上限为 70ch。

## Layout

共享页头与内容区在宽屏上居中，最大宽度为 1280px。写作台首先呈现粉色标题区与桌面照片，再排入角色栏、主稿纸和右侧手册。720px 及以下使用单列稿纸与三列角色按钮，520px 及以下将工作台照片排在标题下方。产品介绍在 620px 及以下把人物照片置于标题之前，标题按完整短语换行。总览的四色指标带在 720px 及以下折成两列。

## Elevation & Depth

粗黑横线划出页头与稿纸的起点。封面标题、摄影和手册用相邻色块分层，弹窗用半透明遮罩圈定当前操作。

## Shapes

封面、角色标签和四色指标使用直角边缘。桌面照片与粉色标题区以斜切边相接，手机上照片横边铺满。输入框和操作按钮使用小圆角，站点标记使用微倾的蓝色星形。

## Components

- **写作台封面**使用编辑桌摄影 `prototype/assets/magazine-desk.webp`，黑底「新建稿件」按钮位于粉色标题区。
- **产品封面**使用人物摄影 `prototype/assets/magazine-editor.webp`。蓝色服装与黄色小册呼应标题色块。
- **角色栏与手册**随当前角色切换。选中的角色带墨色底线，天蓝手册用小书签标记交付与复核信息。
- **稿纸**用黑色顶线、淡色边框划分角色说明、事实依据和本轮要求。正文与复核位于同一阅读流程。
- **导航和操作**以文字和下划线标出当前页，按钮和输入使用带间距的可见焦点。运营视图采用短标题、紧凑列表和文字状态。

## Do's and Don'ts

- **Do** 让摄影的主体与封面文字各自拥有连续的可读区域。
- **Do** 保留稿件状态文字以及按钮的可见焦点。
- **Don't** 把封面摄影延伸到草稿与复核正文背后。
- **Don't** 拆开产品标题中的短语，留下单个汉字占一行。
