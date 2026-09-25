中奖 Logo — 站点运行时只保留这 3 个文件
====================================
本目录只放**站点实际引用**的图标，避免把整套设计素材打进部署产物
（GitHub Pages 会发布整个仓库，素材包会让每次部署多出 7.3MB 且毫无用处）。

保留（被引用，勿删）
------------------------------------
png/logo-32x32.png                   所有页面的 <link rel="icon">
png/logo-64x64.png                   页头品牌 mark（assets/js/site.js）
on-white/apple-touch-icon-180x180.png iOS 添加到主屏图标

已移出的完整素材包
------------------------------------
原目录下的 logo-1024 / master-1024 / png 多分辨率（16~1024）/ on-white 大图 /
on-dark / ico / README 说明，全部**未被站点引用**，已整体移到仓库外：

    ~/Documents/footballdatabackup/brand-kit-20260925/

需要时（做 PWA 图标、印刷物料、深色主题 logo）从那里取。
git 历史里也仍留有全部原文件，随时可 `git log -- assets/img/logo` 找回。

注意
------------------------------------
本 Logo 为 AI 生成作品，用于网站品牌时如涉及商标注册，请自行确认可注册性与近似冲突。
