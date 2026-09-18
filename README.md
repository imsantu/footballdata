# 叕中啦 · 足球数据中心

欧洲五大联赛（英超 / 西甲 / 德甲 / 意甲 / 法甲）与五大次级联赛（英冠 / 西乙 / 德乙 / 法乙 / 意乙）
的赛果统计站点：顶部可自由切换**统计主题**（进球数统计 / 平局统计）与**联赛层级**（五大联赛 / 次级联赛）。

样式、脚本、数据全部拆分成独立文件，便于上传到 GitHub Pages。

## 目录结构

```
.
├── index.html                     首页（站点入口）
├── pages/
│   ├── goals-big5.html            进球数统计 · 五大联赛
│   ├── goals-champ.html           进球数统计 · 次级联赛（占位页，待接入）
│   ├── draws-big5.html            平局统计 · 五大联赛
│   └── draws-champ.html           平局统计 · 次级联赛
└── assets/
    ├── css/
    │   ├── site.css               站点外壳：统一冻结顶栏 + 首页 + 占位页
    │   ├── goals-pc.css           进球数页 · 桌面版样式
    │   ├── draws-big5.css         平局页（五大联赛）样式
    │   └── draws-champ.css        平局页（次级联赛）样式
    ├── font/
    │   ├── ma-shan-zheng.woff2    品牌毛笔楷书（仅「叕中啦」三字，1.6 KB）
    │   └── OFL.txt                SIL Open Font License 1.1
    └── js/
        ├── site.js                统一冻结顶栏（搬迁联赛/年份条）+ 全站唯一主题（★ 加页面改这里）
        ├── data/goals/             进球数 shell + 联赛/赛季 chunk
        ├── view-url.js             单页联赛/赛季 URL 同步（pushState）
        ├── goals-pc.js            进球数页 · 桌面版逻辑
        ├── data/draws-big5/       平局 shell + 联赛/赛季 chunk（五大）
        ├── draws-big5.js          平局逻辑（五大联赛）
        └── data/draws-champ/      平局 shell + 联赛/赛季 chunk（次级）
        └── draws-champ.js         平局逻辑（次级联赛）
```

## 顶部栏与主题

冻结栏铺满浏览器宽度，按 **bilibili 风格三段式** 排列：

| 区域   | 内容                                                                              |
|--------|-----------------------------------------------------------------------------------|
| 左段   | 品牌 logo（圆形足球渐变图标） + 「叕中啦」毛笔楷书（蓝→青→绿渐变文字）                |
| 中段   | 联赛 tab（英超/西甲/德甲/意甲/法甲 + 「五大/次级联赛」整体切换，可横滚）                  |
| 右段   | **统计类型 ▾** · **联赛层级 ▾** · **范围 ▾**（仅平局页） · **主题** 🌗 / ☀ / 🌙 圆方块按钮 |

下方还有一行 **二级 tab 行**，仅在当前页存在年份筛选时出现，且**只放年份**，范围已搬到一级下拉。

### 品牌字体

- 文件：`assets/font/ma-shan-zheng.woff2`（马善政毛笔楷书，仅含「叕中啦」三字，1.6 KB）
- 许可证：[SIL Open Font License 1.1](assets/font/OFL.txt)（OFL 允许自由自托管、商用、修改）
- CSS：`@font-face{font-family:"BrandScript"; src:url(../font/ma-shan-zheng.woff2) format("woff2")}`，
  浏览器读不到时回落到 `Songti SC` / `SimSun` / `serif`，所有平台都能渲染。

### 冻结栏实现要点

- 外壳（`assets/js/site.js`）直接挂在 `<body>` 下，用 `position:fixed` 固定，
  并在正文前插入一个等高占位块（高度写入 CSS 变量 `--site-top-h`），所以内容永远不会被压住，
  也不会出现「筛选条悬浮在页面中间」的情况（绕开了 `position:sticky` 的包含块坑）。
- 页面自带的品牌栏（`.site-head` / `.appbar`）与主题按钮统一隐藏，由外壳呈现。
- 页面里的联赛 tab / 年份条会被外壳**逐个搬进**冻结栏的中段 / 二级行；
  原容器掏空后由 `body .stickynav.site-moved{display:none !important}` 收起，避免留下一条空壳。
- 二级行内容由页面脚本动态注入：`#seasonTabs` 存在就显示，没有就 `display:none`。

### 下拉菜单

- 「统计类型 ▾」对应 `SITE_NAV` 的分组（进球数 / 平局），点选跳到该分组下默认启用页。
- 「联赛层级 ▾」列出当前分组下的所有页（五大 / 次级），未接入的项带「敬请期待」小圆点并不可点。
- 「范围 ▾」（仅平局页有 `#winSwitch` 时显示，默认「近五季」）会读出页面渲染出的 `.wbtn` 列表，
  点击外壳的菜单项时反向触发原按钮的 `click()`，让页面逻辑接管刷新；外壳同时监听「当前选中」变化保持同步。
- 点击 / 外部点击 / `Esc` 三种方式都能关闭菜单；打开时有 0.14s 缩放淡入动效（`@keyframes selIn`）。

### 主题全站统一

- 只有外壳右上一个按钮，自动 → 浅色 → 深色 → 自动 三态循环。
- 「自动」一律为跟随系统外观（`prefers-color-scheme`，不支持时退回本地时间 6:00–18:00 浅色），
  不再出现某个页面按日出日落联网判定、另一个页面按系统判定的割裂。
- 模式同时写进 `qzl_theme` 与 `fbg_theme` 两个历史键，跨页读到的始终是同一个值。
- 进球页自身模板里有 `.theme-btn{position:fixed}` 这条全局规则，
  site.css 用 `body #siteThemeBtn{position:relative !important;...}` 把外壳的主题按钮定位属性复位，
  避免它被拽出 `.site-right` 而盖到下拉菜单上。

## 本地预览

任意静态服务器即可，例如在项目根目录执行：

```bash
python3 -m http.server 8000
# 浏览器打开 http://localhost:8000
```

> 直接双击 `index.html` 也能打开（脚本都是传统 `<script src>`，不走模块加载）。
> 但推荐用服务器预览，与线上 GitHub Pages 的行为完全一致。

## 上传到 GitHub Pages

1. 在 GitHub 新建一个仓库（例如 `football-data`），**不要**勾选初始化 README。
2. 把本目录下的**全部内容**推到仓库（保留 `index.html` 在根目录）：
   ```bash
   git init
   git add .
   git commit -m "足球数据中心：合并进球数与平局统计"
   git branch -M main
   git remote add origin git@github.com:<你的用户名>/football-data.git
   git push -u origin main
   ```
3. 仓库 → **Settings → Pages** → Source 选 `Deploy from a branch`，分支 `main`、目录 `/ (root)`，保存。
4. 等十几秒，访问 `https://<你的用户名>.github.io/football-data/`。
5. 仓库里已放 `.nojekyll`，避免 Jekyll 把 `_` 开头的目录过滤掉。

## 新增一个统计页面

以「次级联赛进球数」为例（页面骨架已备好，只差数据）：

1. 数据落成 `assets/js/goals-champ-data.js`（`window.DATA = {…}`），
   页面逻辑落成 `assets/js/goals-champ.js`，样式落成 `assets/css/goals-champ.css`。
2. 把页面放到 `pages/goals-champ.html`（照抄同主题的现有页面，换掉 css / js 引用即可）。
3. 打开 `assets/js/site.js`，改顶部 `SITE_NAV`：
   ```js
   { id: 'goals-champ', label: '次级联赛', file: 'goals-champ.html', ready: true, desc: '…' }
   ```
   `ready: false` 时导航会带「敬请期待」小圆点，设为 `true` 即恢复正常。
4. 顶部导航和首页卡片都读同一份 `SITE_NAV`，改一处两边同步，不用分别维护。

其他地区联赛同理：在 `SITE_NAV` 里加一个新的主题分组（例如「荷甲 / 葡超」），
或在同一主题下加新的 `items` 条目。

## 关于数据

- 三份报告的**原始统计数据未做任何改动**，仅从单文件 HTML 中原样搬运到
  `assets/js/*-data.js`，落地后做过逐字节 sha256 校验。
- 数据源：
  [openfootball/football.json](https://github.com/openfootball/football.json)、
  [Football-Data.co.uk](https://www.football-data.co.uk/data.php)；队徽来自 Wikipedia。
- 每页页脚标注「本页更新时间」，以页面内标注为准。

## 自动化任务

原先页脚有一枚「每日 09:00 自动更新」的定时任务标识（由本机定时任务拉取赛果后重新生成页面）。
现**已停用并注释保留**：在 `pages/draws-big5.html` 与 `pages/draws-champ.html` 中搜索
`自动化任务标识已停用` 即可看到注释与恢复说明。后续重建自动化任务时，把注释解开、补回图标即可。
