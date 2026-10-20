-- 仅对旧版数据库执行一次；先按 docs/installation-cleanup.md 停止写入并清理旧轮次。
USE aops;
ALTER TABLE raw_host
  ADD COLUMN installation_round varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NULL,
  ADD COLUMN installation_started_at DATETIME NULL,
  ADD COLUMN installation_system varchar(160) NULL;

CREATE TABLE IF NOT EXISTS installation_cleanup (
  host_id varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  round_id varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  system_name varchar(160) NOT NULL,
  state varchar(16) NOT NULL DEFAULT 'pending',
  failures int NOT NULL DEFAULT 0,
  next_attempt_at DATETIME NULL,
  last_error varchar(512) NULL,
  PRIMARY KEY (host_id),
  KEY cleanup_due (state, next_attempt_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
