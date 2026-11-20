---
name: Duke 山海手卷
description: 中文长篇小说工作区，作者可以在一幅青绿山水下编辑章回，对照人物与未解伏笔。
colors:
  paper: "#f5f3e9"
  page: "#f8f6ee"
  ink: "#1b3933"
  dim: "#53665c"
  line: "#bdc7b6"
  green: "#305c48"
  seal: "#944631"
  chapter-current: "#dfe9d9"
  field-paper: "#fffdf5"
typography:
  book-title:
    fontFamily: "Duke Scroll, Noto Serif CJK SC, Songti SC, SimSun, serif"
    fontWeight: 750
    fontSize: "clamp(44px, 5.3vw, 77px)"
    lineHeight: 1.2
    letterSpacing: "0.02em"
  chapter-title:
    fontFamily: "Duke Scroll, Noto Serif CJK SC, Songti SC, SimSun, serif"
    fontWeight: 750
    fontSize: "clamp(30px, 2.7vw, 42px)"
    lineHeight: 1.38
    letterSpacing: "-0.035em"
  manuscript:
    fontFamily: "Noto Serif CJK SC, Songti SC, SimSun, serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.88
  interface:
    fontFamily: "PingFang SC, Noto Sans CJK SC, Microsoft YaHei, sans-serif"
    fontSize: "16px"
    lineHeight: 1.55
  wordmark:
    fontFamily: "Georgia, serif"
    fontWeight: 900
    fontSize: "36px"
    lineHeight: 1
    letterSpacing: "-0.055em"
rounded:
  action: "2px"
  field: "3px"
  dialog: "5px"
spacing:
  dialog-fields: "0.7rem"
  chapter-row: "10px"
  margin-notes: "24px"
components:
  primary:
    backgroundColor: "{colors.green}"
    textColor: "#ffffff"
    padding: "8px 16px"
    rounded: "{rounded.action}"
  quiet:
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "0.4rem 0.75rem"
  navigation:
    textColor: "{colors.dim}"
  seal:
    backgroundColor: "{colors.seal}"
    textColor: "#fff9e9"
    padding: "3px 9px"
  chapter-current:
    backgroundColor: "{colors.chapter-current}"
    textColor: "#214839"
    padding: "10px 11px"
  manuscript:
    textColor: "{colors.ink}"
    typography: "{typography.manuscript}"
    rounded: "{rounded.action}"
  record:
    textColor: "{colors.ink}"
    padding: "0.65rem 0.25rem"
  dialog-field:
    backgroundColor: "{colors.field-paper}"
    rounded: "{rounded.field}"
    padding: "0.55rem 0.7rem"
  preview:
    backgroundColor: "#e9eddf"
    padding: "0.75rem"
---

# Duke 山海手卷

## Overview

**Creative North Star: "山海手卷"**

青绿山水与白鹿铺开一卷浅金色的绢，左侧题写作品名和卷名。画卷下方给正文留出最宽的一栏，作者可以一边写一边核对前文、人物和伏笔。

**Key Characteristics:**

- 卷首使用整幅山水，章节正文落在单色纸面。
- 朱砂印记点出作品类别，未解伏笔使用相同色系。
- 章回目录、正文和页边注共享水平分隔线和墨绿文字。

## Colors

暖绢色用于页面底色，页头和对话框略亮。深墨绿承载标题与正文，青灰用于卷次、字数与保存状态。青瓷色高亮当前章节，深绿用于主要操作。朱砂用于卷首印记、未解伏笔名称及正文插入光标。

## Typography

书名与章名使用本地字库 Duke Scroll，文件为 `prototype/assets/scroll-headlines.woff2`。正文使用系统宋体，桌面字号 18px、行高 1.88，手机字号 17px、行高 1.85。章次、工具和保存状态使用无衬线中文。Duke 字标采用 Georgia 衬线字体。

**The Manuscript Rule.** 章节编辑与续文预览都保留作者的段落和换行。

## Layout

小说首页的卷首图跨越视口，以左侧留白承载书名、右侧保留山势与白鹿。桌面主区居中，最大宽度 1320px，依次为章回目录、正文、人物与伏笔。950px 及以下收紧栏距。730px 及以下改成单列，章节选择器移到正文之前，页边注移到正文之后。365px 及以下两类注释也改为单列。

办公写作台保留六个角色入口、稿纸、角色手册和稿件记录。产品介绍沿用同一幅山水，平台总览则以青瓷、浅绢、雾绿与深墨色分隔指标。各入口由文字导航连接。

## Elevation & Depth

窗外内容在弹窗打开时覆以半透明墨绿。阅读区保持平整，以细线与留白分开章节、工具和注释，章回列表通过浅色底纹和左侧墨线标记当前位置。

## Shapes

卷首和正文都使用平直边缘，操作按钮、输入框和弹窗使用小圆角。朱砂印记为矩形。浏览器图标使用 `prototype/assets/scroll-mark.png`。

## Components

- **卷首**使用 `prototype/assets/shanhai.webp`，书名和卷名由作品数据填入。
- **章回目录**显示章次和标题，当前章节带位置标识。手机使用带文字标签的原生选择器。
- **正文编辑器**直接在纸面上编辑。字数、保存状态、「核对前文」和「续写本章」位于正文下方。
- **书架与设定**共用有标题和关闭按钮的对话框。书架显示作品与章数，人物册和伏笔簿以列表进入编辑。页边注仅呈现当前章节可见的人物与未解伏笔。
- **续文预览**将候选文字呈现在淡青灰纸面，作者确认「接到正文末尾」后才合入手稿。

## Do's and Don'ts

- **Do** 为书名、卷名和正文使用可选择、可缩放的 HTML 文字。
- **Do** 保留当前章次、保存状态、键盘焦点与续写确认操作。
- **Don't** 在正文背后铺山水图。
- **Don't** 将预览中的模型续文直接当作作者已确认的段落。
