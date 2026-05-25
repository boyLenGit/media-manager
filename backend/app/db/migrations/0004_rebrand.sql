-- 0004 改品牌名 (mediahub → media-manager)
-- 已部署的旧实例 0001/0002 已经应用过,这一次更新现有记录里的品牌字符串

-- 更新自定义协议的 scheme
UPDATE playback_target
   SET config_json = REPLACE(config_json, '"scheme":"mediahub"', '"scheme":"media-manager"')
 WHERE target_type = 'custom_protocol'
   AND config_json LIKE '%"scheme":"mediahub"%';
