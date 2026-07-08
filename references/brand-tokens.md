# 品牌 token 契约 -- 7 主题体系(sansheng-distill)

> **单一事实源**。`templates/page-skeleton.html` 的 `<style>` token 块与本文档一一对应;改值必须两处同步(先改哪边都行,但 commit 前必须一致)。
> 校验:`scripts/verify_page.py`(Task 6)对每张产物页跑 Zero Hex lint(见 §7)。
> 抄录说明:6 套现有主题取值抄自蓝本 `个人网站/web/public/booknotes/01-聪明的投资者.html` L8-202;唯一系统性改动 = 衬线字体栈统一补 `"Noto Serif SC"` 兜底(Global Constraints 硬要求),以及 warm-paper 绿金品牌对齐(§3)。

---

## 1. token 名契约(21 个,与存量 48 本同名,extract 管线兼容)

组件样式只许引用这 21 个名字。**禁止新增 token 名、禁止改名**(每书 signature 只许覆盖值,见 §5)。

| token | 语义 | 使用注意 |
|---|---|---|
| `--ink` | 正文主色 | 大面积正文一律用它 |
| `--muted` | 次要文字 / 说明 / 出处 | |
| `--ink-soft` | 软正文(lede / 段落) | |
| `--ink-soft-2` | 卡片内正文 | |
| `--paper` | 纸面色(卡底 / **ink 底上的反色前景**) | 骨架组件反白统一 `color:var(--paper)`(暗主题自动反转,免每主题覆盖) |
| `--paper-deep` | 深纸面(banner 底) | |
| `--line` | 边框 / 分隔线 | |
| `--red` | 强调·警示 / eyebrow / thesis 竖线 | |
| `--blue` | 强调·链接 / 规则关键词 | |
| `--green` | 强调·行动 / 正向(品牌绿族) | |
| `--gold` | 强调·装饰 / 引用 / 时间线(品牌金族) | 浅底主题下对比度约 2.8:1,只用于大字号 / 边框 / 装饰底,**禁做正文小字前景** |
| `--white` | 高光底 / 亮面 | 暗主题下语义反转为深色(brand-dark 取 `#0B111A`);骨架组件基本不用,保留名契约供 signature 层 |
| `--surface` | 卡片底(半透明) | |
| `--surface-strong` | 强卡底(thesis / 弹层) | |
| `--bar-bg` | 吸顶 tab 条 / 浮动控件底 | |
| `--font-body` | 正文字体栈 | 衬线栈**必带** `"Songti SC","Noto Serif SC"` 兜底 |
| `--font-display` | 标题 / UI 字栈 | 每书 signature 可换(§5) |
| `--bg` | 页面背景(可含渐变) | 纯渐变时 `backgroundColor` 计算值为 transparent,verify 冒烟依赖此差异 |
| `--shadow` | 卡片投影 | |
| `--tint-accent` | 强调淡底(hover / 装饰) | |
| `--tint-accent-strong` | 强调淡底·强(高亮 / `.flash`) | |

---

## 2. 七套主题完整取值

机制:`:root` = warm-paper 默认;其余 6 套用 `body[data-theme="…"]` 整块覆盖同一组 token,**换肤不碰布局**。
主题记忆:localStorage key `bd:{book_slug}:theme`。
切换控件契约:容器 `.theme-picker`(默认收起,`data-open="0"`)+ 触发按钮 `.tp-trigger` + 竖列弹层 `.tp-menu` 内 7 颗 `[data-theme-pick="{主题名}"]`(verify_page.py 先开弹层再点主题项冒烟,见 §6)。

### 2.1 warm-paper 暖纸典藏(默认,写在 `:root`)

`--green`/`--gold` 及其衍生(`--tint-accent*`、`--bg` 的 radial)为品牌对齐后的新值,变更依据见 §3。

```css
:root{
  --ink:#171411;
  --muted:#6d6258;
  --paper:#f8f2e7;
  --paper-deep:#ece1cf;
  --line:#d8c8af;
  --red:#b9422f;
  --blue:#245f73;
  --green:#177A5C;
  --gold:#B8892F;
  --white:#fffaf0;
  --surface:rgba(255,250,240,.62);
  --surface-strong:rgba(255,250,240,.72);
  --bar-bg:rgba(248,242,231,.95);
  --font-body:"Songti SC","Noto Serif SC","Noto Serif CJK SC",Georgia,serif;
  --font-display:"PingFang SC","Microsoft YaHei",sans-serif;
  --bg:radial-gradient(circle at 22% 12%, rgba(184,137,47,.18), transparent 28rem),
       linear-gradient(135deg,#fbf6ec 0%,#efe1ca 100%);
  --shadow:0 18px 50px rgba(55,38,19,.14);
  --tint-accent:rgba(184,137,47,.12);
  --tint-accent-strong:rgba(184,137,47,.15);
  --ink-soft:#3d332b;
  --ink-soft-2:#44392f;
}
```

### 2.2 minimal 极简学术

```css
body[data-theme="minimal"]{
  --ink:#111111; --muted:#6b6b6b; --paper:#ffffff; --paper-deep:#f6f6f4; --line:#e4e4e0;
  --red:#111111; --blue:#2f4858; --green:#2f4858; --gold:#2f4858; --white:#ffffff;
  --surface:#fafaf8; --surface-strong:#f2f2ef; --bar-bg:rgba(248,248,246,.95);
  --font-body:-apple-system,"PingFang SC","Helvetica Neue","Microsoft YaHei",sans-serif;
  --font-display:"PingFang SC","Helvetica Neue","Microsoft YaHei",sans-serif;
  --bg:#ffffff; --shadow:0 12px 40px rgba(17,17,17,.06);
  --tint-accent:rgba(47,72,88,.10); --tint-accent-strong:rgba(47,72,88,.14);
  --ink-soft:#2a2a2a; --ink-soft-2:#333333;
}
```

### 2.3 dark 夜读深空(存量暖褐夜读,保留不动)

```css
body[data-theme="dark"]{
  --ink:#ece1cf; --muted:#a89a86; --paper:#221d18; --paper-deep:#2a241e; --line:#3a3128;
  --red:#e07a66; --blue:#7fb0c4; --green:#9bbf8e; --gold:#d9a441; --white:#fffaf0;
  --surface:rgba(58,49,40,.45); --surface-strong:rgba(58,49,40,.6); --bar-bg:rgba(34,29,24,.95);
  --font-body:"Songti SC","Noto Serif SC","Noto Serif CJK SC",Georgia,serif;
  --font-display:"PingFang SC","Microsoft YaHei",sans-serif;
  --bg:radial-gradient(circle at 22% 12%, rgba(194,135,45,.08), transparent 28rem),
       linear-gradient(135deg,#1a1714 0%,#221d18 100%);
  --shadow:0 18px 50px rgba(0,0,0,.4);
  --tint-accent:rgba(217,164,65,.14); --tint-accent-strong:rgba(217,164,65,.18);
  --ink-soft:#d8ccb8; --ink-soft-2:#c9bca6;
}
```

### 2.4 ink-wash 东方水墨

```css
body[data-theme="ink-wash"]{
  --ink:#1a1a1a; --muted:#7a7468; --paper:#f4f0e6; --paper-deep:#eae3d2; --line:#cfc6b0;
  --red:#9c2b1f; --blue:#3a352d; --green:#6b6354; --gold:#9c2b1f; --white:#fbf8ef;
  --surface:rgba(255,253,247,.5); --surface-strong:rgba(255,253,247,.7); --bar-bg:rgba(244,240,230,.95);
  --font-body:"Songti SC","STKaiti","KaiTi","Noto Serif SC","Noto Serif CJK SC",Georgia,serif;
  --font-display:"Songti SC","STSong","Noto Serif SC",serif;
  --bg:#f4f0e6; --shadow:0 14px 44px rgba(60,50,35,.10);
  --tint-accent:rgba(156,43,31,.08); --tint-accent-strong:rgba(156,43,31,.12);
  --ink-soft:#3a352d; --ink-soft-2:#2e2a23;
}
```

### 2.5 vintage-editorial 复古编辑

```css
body[data-theme="vintage-editorial"]{
  --ink:#1f1a15; --muted:#8c8176; --paper:#f5f3ee; --paper-deep:#ebe6dc; --line:#d9d1c4;
  --red:#c05a4a; --blue:#4a5568; --green:#6b7064; --gold:#b8893e; --white:#faf8f2;
  --surface:rgba(250,248,242,.55); --surface-strong:rgba(250,248,242,.72); --bar-bg:rgba(245,243,238,.95);
  --font-body:"PingFang SC","Microsoft YaHei","Helvetica Neue",sans-serif;
  --font-display:"Songti SC","STSong","Noto Serif SC","Noto Serif CJK SC",Georgia,serif;
  --bg:#f5f3ee; --shadow:0 14px 44px rgba(50,38,28,.08);
  --tint-accent:rgba(192,90,74,.08); --tint-accent-strong:rgba(192,90,74,.12);
  --ink-soft:#3d3530; --ink-soft-2:#4a403b;
}
```

### 2.6 paper-ink 纸墨风

```css
body[data-theme="paper-ink"]{
  --ink:#1a1a1a; --muted:#7a7268; --paper:#faf9f7; --paper-deep:#f0ece6; --line:#d4cdc2;
  --red:#b53a3a; --blue:#3d4f5f; --green:#5a6b56; --gold:#b53a3a; --white:#fdfbf7;
  --surface:rgba(253,251,247,.5); --surface-strong:rgba(253,251,247,.7); --bar-bg:rgba(250,249,247,.95);
  --font-body:"STKaiti","KaiTi","Songti SC","Noto Serif SC","Noto Serif CJK SC",Georgia,serif;
  --font-display:"Songti SC","STSong","Noto Serif SC","Noto Serif CJK SC",Georgia,serif;
  --bg:#faf9f7; --shadow:0 12px 38px rgba(30,25,20,.06);
  --tint-accent:rgba(181,58,58,.07); --tint-accent-strong:rgba(181,58,58,.10);
  --ink-soft:#2d2a26; --ink-soft-2:#36322d;
}
```

### 2.7 brand-dark 深空(新增第 7 主题)

```css
body[data-theme="brand-dark"]{
  --ink:#CBD4E0; --muted:#8A94A6; --ink-soft:#8A94A6; --ink-soft-2:rgba(138,148,166,.7);
  --paper:#0B111A; --paper-deep:#05080D; --line:rgba(232,238,245,.10);
  --red:#E2654E; --blue:#5FA8C9; --green:#34D399; --gold:#E8B84B; --white:#0B111A;
  --surface:rgba(255,255,255,.04); --surface-strong:rgba(13,18,26,.72);
  --bar-bg:rgba(5,8,13,.95); --shadow:0 18px 50px rgba(0,0,0,.5);
  --tint-accent:rgba(52,211,153,.10); --tint-accent-strong:rgba(52,211,153,.20);
  --bg:radial-gradient(1200px 800px at 20% -10%, rgba(14,159,110,.12), transparent 60%), #05080D;
}
```

- 设计意图:`--bg` 对齐站壳 `#05080D` 系,accent 走品牌绿 `#34D399` / 品牌金 `#E8B84B`,消掉现 dark 暖褐与站壳蓝黑「两种黑打架」。
- `--white:#0B111A` 是**故意的语义反转**:`--white` 承担"反色底上的高光面",暗主题下反转为深色,让沿用 `--white` 的存量组件语法自动可读。
- 字体:**不覆盖** `--font-body`/`--font-display`,继承 `:root` 的衬线栈(深空夜读仍用衬线)。
- 对比度实测(2026-07-02):`--ink` 对 `--paper` 约 12.5:1,`--muted` 对 `--paper` 约 6.2:1,`--green` 对 `--paper` 约 9:1,均过 AA。**本块为初稿值,后续如过对比度检查需微调,微调后必须回写本文档。**

### 2.8 主题专属组件微调规则(token 块之外,零 hex)

骨架允许少量"每主题的组件微调",但**只许写 `var(--*)` 或 `content` 字符,禁止 hex**(这些规则不在 lint 的 token 块白名单里):

```css
body[data-theme="minimal"] .thesis{border-left-color:var(--ink)}
body[data-theme="ink-wash"] .quote::before{content:"\300E";color:var(--red);font-family:var(--font-body)}
body[data-theme="vintage-editorial"] .quote::before{content:"\275D";color:var(--red)}
body[data-theme="paper-ink"] .quote::before{content:"\2767";color:var(--red)}
```

蓝本里 `[data-theme="dark"] .tab[aria-selected]` / `[data-source]::after` 的 hex 补丁**不再需要**:骨架把 ink 底反色统一写成 `color:var(--paper)`(而非蓝本的 `var(--white)`),七套主题自动全对。

---

## 3. warm-paper 品牌对齐(v1 变更记录)

| token | 旧值(蓝本) | 新值 | 理由 |
|---|---|---|---|
| `--green` | `#4d6f48` | `#177A5C` | 站壳品牌绿 `#0E9F6E`/`#34D399` 的同族深化,适配暖纸低饱和语境;对 `--paper #f8f2e7` 对比度约 4.7:1,过 AA 正文线 |
| `--gold` | `#c2872d` | `#B8892F` | 站壳品牌金 `#E8B84B` 的同族深化;对 `--paper` 约 2.8:1,仅限装饰 / 大字号 / 边框(见 §1 注意列) |
| `--tint-accent` | `rgba(194,135,45,.12)` | `rgba(184,137,47,.12)` | 金色淡底跟随新 `--gold`(184,137,47 = #B8892F) |
| `--tint-accent-strong` | `rgba(194,135,45,.15)` | `rgba(184,137,47,.15)` | 同上 |
| `--bg` radial | `rgba(194,135,45,.18)` | `rgba(184,137,47,.18)` | 背景金晕跟随新 `--gold` |

- **对比度校验后可微调,微调后回写本文档**(与骨架同步)。
- 存量 48 本**零迁移**:旧页不动,新值只进新产物;dark 等其余 5 主题内的旧金色 rgba 一律保留原值。

---

## 4. 脑图配色约定(M03,markmap)

| 部位 | token |
|---|---|
| 主干(根节点) | `--ink` |
| 分支(一级起循环) | `--red` → `--blue` → `--green` → `--gold` 循环 |
| 节点底 | `--surface` |
| 连线 | `--line` |

实现(2026-07-03 精修):初始渲染时从 `getComputedStyle(document.body)` 读上述 var,传一个 `color` 回调给 `Markmap.create`:按 `node.state.path` 的一级分支段循环取 `--red/--blue/--green/--gold`、根节点取 `--ink`;连线 / 叶子圆点 / 节点文字则用 CSS 覆盖 markmap 注入的 SVG(`.bd-mindmap-wrap svg.markmap …`,连线 `--line`、文字 `--ink`、层级字号)。切主题时 `initThemes` 调 `window.__bdMindmapRetheme()` 重算颜色回调并重绘,**换肤自动跟随**,全程不写死色值。

---

## 5. 「品牌锁八成,书魂放两成」边界表

| 维度 | 锁死(八成,家族感) | 放开(两成,书魂) |
|---|---|---|
| 底色体系 | 7 主题全部 token 值(§2) | -- |
| 正文字体 | `--font-body` 栈 | -- |
| 组件语法 | 类名 + DOM 契约(page-skeleton.html) | -- |
| token 名 | 21 个名字(§1),禁增禁改 | -- |
| display 字体 | -- | `--font-display` 每书可换(仍须带 CJK 兜底) |
| signature 元素 | -- | hero 区一个每书专属视觉记号(纹样 / 编号 / 图形),限一处 |
| accent 色 | -- | `--red`/`--blue`/`--green`/`--gold` 允许 oklch 同族微调(同色相 ±10°,明度饱和小步) |

放开项的操作规矩:**只许通过覆盖 token 值实现**(在页面自己的 token 块里),禁新增 token 名、禁在组件样式里写死色值。

### 5.1 圆角三档 scale token(v4 批次C,Q7-11)

治「圆角 0/4/6/10/999 五档混用」:`:root` 定义三档、组件收敛引用(与色 token 同治理逻辑,主题无关不随换肤,故只在 `:root`、不入 `body[data-theme]` 覆盖块)。

| token | 值 | 语义 |
|---|---|---|
| `--r-card` | `0` | 内容卡(方角家族语言,`.ci`/`.rule-card`/`.sim-card` 等) |
| `--r-ui` | `6px` | 容器级 UI 件(`.tab`/`.next-cta`/预告卡/上下文条 totoc 等) |
| `--r-pill` | `999px` | 胶囊(chip/tab-sub/圆标) |

- 新组件圆角**不得发明第四档**,一律取三档之一。既有 `.tp-menu`(弹层)允许留大一档(8-10px);深色脑图画布 `#bd-mindmap`(16px)属特例画布,不进 scale。
- 这三个是**非色 token**,不参与 §7 Zero-Hex 扫描(只扫 hex 色);extract 管线只映射 §1 的 21 个色 token,radius token 不影响它。

---

## 6. fixed 控件规矩

- `theme-picker` 放**右下**(`position:fixed; right/bottom`),`src-toggle` 挨着它 -- 避开站壳右上 mini-player 区;新增 fixed 元素一律优先放底部。
- 上站后 extract 按 `.theme-picker` / `.src-toggle` 类名剔除浮层(站壳有自己的控件),所以浮动控件**必须用这两个约定类名**。
- **主题切换器 = 触发按钮 + 竖列弹层(2026-07-03 改)**:`.theme-picker` 默认**收起**为一个小触发按钮 `.tp-trigger`(文字「主题」+ 极简 SVG caret,禁 emoji 当图标);点它切 `.theme-picker[data-open="1"]` 弹出竖向单列菜单 `.tp-menu`(`flex-direction:column`,窄宽约 172px,右对齐、不遮左侧正文)。菜单内放 7 颗 `<button data-theme-pick="{主题名}">`;当前生效项由脚本写 `aria-current="true"` 高亮。点主题项应用并收起;点弹层外 / 按 Esc 收起。切主题后脚本调 `window.__bdMindmapRetheme()` 让脑图配色跟随换肤。
- 切换契约不变:`[data-theme-pick]` 仍是主题按钮选择器;verify_page.py 主题冒烟**先点 `.tp-trigger` 开弹层、再点某主题项**断言 body 背景变化(菜单收起时按钮不可见、直接点会失败)。
- **菜单第一颗按钮不得是默认主题 warm-paper**:verify 冒烟挑「与当前主题不同且有具名 token 块」的第一颗并点它断言背景变化,点默认主题背景不变会误报。骨架把 `brand-dark`(品牌主题)放菜单第一位。

---

## 7. Zero Hex Colors 规则(lint 强制)

规则原文(实现计划 Global Constraints):

> **Zero Hex Colors**:组件样式只用 `var(--*)`;hex 只允许出现在 `:root{}` 与 `body[data-theme=…]{}` token 定义块内。

执行方式:`scripts/verify_page.py` 的 `lint_html()` 把 `:root{…}` 与 `body[data-theme=…]{…}` 块整块剔除后,对剩余 CSS 扫 `#hex`,命中即违规(exit 1)。

写法要求(不满足会误伤或漏检):

1. token 块选择器必须写成 `:root{…}` 或 `body[data-theme="x"]{…}`,且**块内只放声明**(不得出现嵌套 `{}`,注释里也不得出现 `}`)。
2. 主题组件微调规则(如 `body[data-theme="minimal"] .thesis{…}`,选择器后带后代)**不算 token 块**,内部禁 hex。
3. `rgba(…)` 不在 hex lint 范围内,但组件样式仍应优先 `var(--*)`;rgba 只用于阴影 / 遮罩等无对应 token 的透明层。
4. CSS 里的 id 选择器避免取形如 `#abc123` 的 3-8 位十六进制字符名(会被 lint 误判);现有 `#bd-mindmap` 安全。
