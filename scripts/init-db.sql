-- ZenAlpha Database Initialization
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS zenalpha DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE zenalpha;

-- ============================================================
-- data-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS instrument (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100),
    sector VARCHAR(50),
    market_cap DECIMAL(20,2),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_sector (sector)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS kline (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    instrument_id BIGINT NOT NULL,
    timeframe VARCHAR(5) NOT NULL,
    timestamp DATETIME NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume BIGINT NOT NULL,
    UNIQUE KEY uk_kline (instrument_id, timeframe, timestamp),
    FOREIGN KEY (instrument_id) REFERENCES instrument(id) ON DELETE CASCADE,
    INDEX idx_instrument_tf (instrument_id, timeframe),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB;

-- ============================================================
-- signal-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS signal_record (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    signal_type VARCHAR(5) NOT NULL,
    level VARCHAR(5) NOT NULL,
    timestamp DATETIME NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    strength DECIMAL(10,4),
    score DECIMAL(10,4),
    source_lesson VARCHAR(20),
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_instrument_type (instrument, signal_type),
    INDEX idx_created (created_at),
    INDEX idx_score (score DESC)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS scan_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    signal_id BIGINT NOT NULL,
    score DECIMAL(10,4) NOT NULL,
    rank INT NOT NULL,
    scan_time TIMESTAMP NOT NULL,
    FOREIGN KEY (signal_id) REFERENCES signal_record(id) ON DELETE CASCADE,
    INDEX idx_scan_time (scan_time),
    INDEX idx_score (score DESC)
) ENGINE=InnoDB;

-- ============================================================
-- backtest-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS backtest_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_cash DECIMAL(20,2) NOT NULL,
    total_return DECIMAL(10,6),
    annualized_return DECIMAL(10,6),
    sharpe_ratio DECIMAL(10,4),
    sortino_ratio DECIMAL(10,4),
    calmar_ratio DECIMAL(10,4),
    max_drawdown DECIMAL(10,6),
    win_rate DECIMAL(10,4),
    profit_factor DECIMAL(10,4),
    total_trades INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_instrument (instrument),
    INDEX idx_created (created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS trade (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    backtest_id BIGINT NOT NULL,
    instrument VARCHAR(20) NOT NULL,
    direction VARCHAR(5) NOT NULL,
    entry_price DECIMAL(20,8) NOT NULL,
    exit_price DECIMAL(20,8) NOT NULL,
    entry_time DATETIME NOT NULL,
    exit_time DATETIME NOT NULL,
    quantity DECIMAL(20,8) NOT NULL,
    pnl DECIMAL(20,8),
    pnl_pct DECIMAL(10,6),
    signal_type VARCHAR(5),
    exit_reason VARCHAR(50),
    FOREIGN KEY (backtest_id) REFERENCES backtest_result(id) ON DELETE CASCADE,
    INDEX idx_backtest (backtest_id)
) ENGINE=InnoDB;

-- ============================================================
-- user-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS `user` (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'USER',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS watchlist (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    name VARCHAR(100) NOT NULL,
    instruments JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    INDEX idx_user (user_id)
) ENGINE=InnoDB;

-- ============================================================
-- notification-service tables
-- ============================================================

CREATE TABLE IF NOT EXISTS notification_config (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    channel VARCHAR(20) NOT NULL,
    target VARCHAR(255) NOT NULL,
    signal_types JSON,
    min_score DECIMAL(10,4) DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    INDEX idx_user_channel (user_id, channel)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notification_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_id BIGINT NOT NULL,
    signal_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (config_id) REFERENCES notification_config(id) ON DELETE CASCADE,
    INDEX idx_config (config_id),
    INDEX idx_sent (sent_at)
) ENGINE=InnoDB;

-- ============================================================
-- Apollo Config DB (minimal init for K8s)
-- ============================================================

CREATE DATABASE IF NOT EXISTS ApolloConfigDB DEFAULT CHARACTER SET utf8mb4;
CREATE DATABASE IF NOT EXISTS ApolloPortalDB DEFAULT CHARACTER SET utf8mb4;
