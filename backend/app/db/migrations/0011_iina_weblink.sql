-- 0011_iina_weblink.sql
-- 新增"用 IINA 打开"播放目标。
--
-- 背景:HEVC/H.265 等浏览器不支持网页直播的视频,之前只能引导用户"复制链接
-- 手动粘贴到本地播放器",多一步操作。IINA(macOS 上的开源播放器)官方通过
-- Safari 扩展 SafariExtensionHandler.swift 里的 launchIINA() 自行注册了
-- iina://weblink?url=<url> 协议,只要用户装了 IINA,浏览器点击这个链接就会
-- 自动唤起 IINA 直接播放对应 URL,不需要我们额外开发任何"协议助手"程序
-- (custom_protocol 那条路线之所以从未落地,正是因为需要自己写一个从零注册
-- scheme 的本地助手程序,工作量大且未排期)。
--
-- 默认禁用,因为只对装了 IINA 的用户(主要是 macOS)有意义,由用户在
-- 设置 → 播放目标 里按需启用。

INSERT OR IGNORE INTO playback_target (name, target_type, enabled, config_json, sort_order)
SELECT '用 IINA 打开', 'iina_weblink', 0, '{}', 35
WHERE NOT EXISTS (
    SELECT 1 FROM playback_target WHERE target_type = 'iina_weblink'
);
