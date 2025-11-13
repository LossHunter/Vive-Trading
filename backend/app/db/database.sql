CREATE TABLE "upbit_markets" (
  "market" text PRIMARY KEY,
  "korean_name" text,
  "english_name" text,
  "created_at" timestamptz DEFAULT (now())
);

CREATE TABLE "upbit_ticker" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "trade_price" numeric(20,8),
  "opening_price" numeric(20,8),
  "high_price" numeric(20,8),
  "low_price" numeric(20,8),
  "prev_closing_price" numeric(20,8),
  "change" text,
  "signed_change_rate" numeric(10,6),
  "acc_trade_price_24h" numeric(30,10),
  "acc_trade_volume_24h" numeric(30,10),
  "timestamp" bigint,
  "collected_at" timestamptz DEFAULT (now()),
);

CREATE TABLE "upbit_candles_minute3" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "candle_date_time_utc" timestamptz NOT NULL,
  "candle_date_time_kst" timestamptz,
  "opening_price" numeric(20,8),
  "high_price" numeric(20,8),
  "low_price" numeric(20,8),
  "trade_price" numeric(20,8),
  "prev_closing_price" numeric(20,8),
  "change_price" numeric(20,8),
  "change_rate" numeric(10,6),
  "candle_acc_trade_price" numeric(30,10),
  "candle_acc_trade_volume" numeric(30,10),
  "unit" int DEFAULT 3,
  "timestamp" bigint,
  "collected_at" timestamptz DEFAULT (now()),
);

CREATE TABLE "upbit_day_candles" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "candle_date_time_utc" timestamptz NOT NULL,
  "candle_date_time_kst" timestamptz,
  "opening_price" numeric(20,8),
  "high_price" numeric(20,8),
  "low_price" numeric(20,8),
  "trade_price" numeric(20,8),
  "prev_closing_price" numeric(20,8),
  "change_price" numeric(20,8),
  "change_rate" numeric(10,6),
  "candle_acc_trade_price" numeric(30,10),
  "candle_acc_trade_volume" numeric(30,10),
  "timestamp" bigint,
  "collected_at" timestamptz DEFAULT (now()),
  "raw_json" jsonb
);

CREATE TABLE "upbit_rsi" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "candle_date_time_utc" timestamptz NOT NULL,
  "period" int DEFAULT 14,
  "au" numeric(18,8),
  "ad" numeric(18,8),
  "rs" numeric(18,8),
  "rsi" numeric(10,4),
  "calculated_at" timestamptz DEFAULT (now())
);

CREATE TABLE "upbit_indicators" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "candle_date_time_utc" timestamptz NOT NULL,
  "interval" text,
  "ema12" numeric(20,8),
  "ema26" numeric(20,8),
  "macd" numeric(20,8),
  "macd_signal" numeric(20,8),
  "macd_hist" numeric(20,8),
  "rsi14" numeric(10,4),
  "atr14" numeric(20,8),
  "bb_upper" numeric(20,8),
  "bb_middle" numeric(20,8),
  "bb_lower" numeric(20,8),
  "calculated_at" timestamptz DEFAULT (now())
);

CREATE TABLE "upbit_trades" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "trade_timestamp" bigint,
  "trade_date_time_utc" timestamptz,
  "trade_price" numeric(20,8),
  "trade_volume" numeric(30,10),
  "ask_bid" text,
  "prev_closing_price" numeric(20,8),
  "change" text,
  "sequential_id" bigint UNIQUE,
  "collected_at" timestamptz DEFAULT (now()),
);

CREATE TABLE "upbit_orderbook" (
  "id" bigserial PRIMARY KEY,
  "market" text NOT NULL,
  "timestamp" bigint,
  "total_ask_size" numeric(30,10),
  "total_bid_size" numeric(30,10),
  "collected_at" timestamptz DEFAULT (now())
);

CREATE TABLE "upbit_accounts" (
  "id" bigserial PRIMARY KEY,
  "account_id" uuid,
  "currency" text NOT NULL,
  "balance" numeric(30,10),
  "locked" numeric(30,10),
  "avg_buy_price" numeric(30,10),
  "avg_buy_price_modified" boolean,
  "unit_currency" text,
  "collected_at" timestamptz DEFAULT (now()),
);

CREATE INDEX "idx_ticker_market_collected" ON "upbit_ticker" ("market", "collected_at");

CREATE UNIQUE INDEX "ux_candle3_market_time" ON "upbit_candles_minute3" ("market", "candle_date_time_utc");

CREATE UNIQUE INDEX "ux_day_candle_market_time" ON "upbit_day_candles" ("market", "candle_date_time_utc");

CREATE UNIQUE INDEX "ux_rsi_market_time_period" ON "upbit_rsi" ("market", "candle_date_time_utc", "period");

CREATE UNIQUE INDEX "ux_indicators_market_time" ON "upbit_indicators" ("market", "candle_date_time_utc", "interval");

CREATE UNIQUE INDEX "ux_accounts_account_currency" ON "upbit_accounts" ("account_id", "currency");

COMMENT ON TABLE "upbit_markets" IS 'Upbit 거래가능 마켓 기본정보';

COMMENT ON COLUMN "upbit_markets"."market" IS '마켓 코드 (예: KRW-BTC)';

COMMENT ON COLUMN "upbit_markets"."korean_name" IS '한글명 (예: 비트코인)';

COMMENT ON COLUMN "upbit_markets"."english_name" IS '영문명 (예: Bitcoin)';

COMMENT ON COLUMN "upbit_markets"."created_at" IS '행 생성 시각 (UTC)';

COMMENT ON TABLE "upbit_ticker" IS 'Upbit 현재가 정보 (/ticker API)';

COMMENT ON COLUMN "upbit_ticker"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_ticker"."market" IS '마켓 코드 FK (예: KRW-BTC)';

COMMENT ON COLUMN "upbit_ticker"."trade_price" IS '현재가 (최근 체결가)';

COMMENT ON COLUMN "upbit_ticker"."opening_price" IS '시가 (당일 첫 거래가)';

COMMENT ON COLUMN "upbit_ticker"."high_price" IS '고가 (당일 최고가)';

COMMENT ON COLUMN "upbit_ticker"."low_price" IS '저가 (당일 최저가)';

COMMENT ON COLUMN "upbit_ticker"."prev_closing_price" IS '전일 종가';

COMMENT ON COLUMN "upbit_ticker"."change" IS '상승/하락/보합 상태 (RISE/FALL/EVEN)';

COMMENT ON COLUMN "upbit_ticker"."signed_change_rate" IS '전일 대비 등락률 (%)';

COMMENT ON COLUMN "upbit_ticker"."acc_trade_price_24h" IS '최근 24시간 누적 거래금액';

COMMENT ON COLUMN "upbit_ticker"."acc_trade_volume_24h" IS '최근 24시간 누적 거래량';

COMMENT ON COLUMN "upbit_ticker"."timestamp" IS 'Upbit 서버 타임스탬프(ms)';

COMMENT ON COLUMN "upbit_ticker"."collected_at" IS '데이터 수집 시각(UTC)';

COMMENT ON COLUMN "upbit_ticker"."raw_json" IS '원본 JSON 전체 저장';

COMMENT ON TABLE "upbit_candles_minute3" IS 'Upbit 3분봉 캔들 데이터 (/v1/candles/minutes/3)';

COMMENT ON COLUMN "upbit_candles_minute3"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_candles_minute3"."market" IS '마켓 코드 FK (예: KRW-BTC)';

COMMENT ON COLUMN "upbit_candles_minute3"."candle_date_time_utc" IS 'UTC 기준 캔들 시각';

COMMENT ON COLUMN "upbit_candles_minute3"."candle_date_time_kst" IS 'KST 기준 캔들 시각';

COMMENT ON COLUMN "upbit_candles_minute3"."opening_price" IS '시가 (Open)';

COMMENT ON COLUMN "upbit_candles_minute3"."high_price" IS '고가 (High)';

COMMENT ON COLUMN "upbit_candles_minute3"."low_price" IS '저가 (Low)';

COMMENT ON COLUMN "upbit_candles_minute3"."trade_price" IS '종가 (Close)';

COMMENT ON COLUMN "upbit_candles_minute3"."prev_closing_price" IS '전일 종가';

COMMENT ON COLUMN "upbit_candles_minute3"."change_price" IS '전일 대비 가격 변화량';

COMMENT ON COLUMN "upbit_candles_minute3"."change_rate" IS '전일 대비 변화율 (%)';

COMMENT ON COLUMN "upbit_candles_minute3"."candle_acc_trade_price" IS '캔들 누적 거래금액';

COMMENT ON COLUMN "upbit_candles_minute3"."candle_acc_trade_volume" IS '캔들 누적 거래량';

COMMENT ON COLUMN "upbit_candles_minute3"."unit" IS '캔들 단위(3분봉 고정)';

COMMENT ON COLUMN "upbit_candles_minute3"."timestamp" IS 'Upbit 서버 타임스탬프(ms)';

COMMENT ON COLUMN "upbit_candles_minute3"."collected_at" IS '데이터 수집 시각';

COMMENT ON COLUMN "upbit_candles_minute3"."raw_json" IS '원본 JSON 데이터';

COMMENT ON TABLE "upbit_day_candles" IS 'Upbit 일봉 캔들 데이터 (/v1/candles/days)';

COMMENT ON COLUMN "upbit_day_candles"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_day_candles"."market" IS '마켓 코드 FK (예: KRW-BTC)';

COMMENT ON COLUMN "upbit_day_candles"."candle_date_time_utc" IS 'UTC 기준 캔들 시각';

COMMENT ON COLUMN "upbit_day_candles"."candle_date_time_kst" IS 'KST 기준 캔들 시각';

COMMENT ON COLUMN "upbit_day_candles"."opening_price" IS '시가 (Open)';

COMMENT ON COLUMN "upbit_day_candles"."high_price" IS '고가 (High)';

COMMENT ON COLUMN "upbit_day_candles"."low_price" IS '저가 (Low)';

COMMENT ON COLUMN "upbit_day_candles"."trade_price" IS '종가 (Close)';

COMMENT ON COLUMN "upbit_day_candles"."prev_closing_price" IS '전일 종가';

COMMENT ON COLUMN "upbit_day_candles"."change_price" IS '전일 대비 가격 변화량';

COMMENT ON COLUMN "upbit_day_candles"."change_rate" IS '전일 대비 변화율 (%)';

COMMENT ON COLUMN "upbit_day_candles"."candle_acc_trade_price" IS '일봉 누적 거래금액';

COMMENT ON COLUMN "upbit_day_candles"."candle_acc_trade_volume" IS '일봉 누적 거래량';

COMMENT ON COLUMN "upbit_day_candles"."timestamp" IS 'Upbit 서버 타임스탬프(ms)';

COMMENT ON COLUMN "upbit_day_candles"."collected_at" IS '데이터 수집 시각';

COMMENT ON COLUMN "upbit_day_candles"."raw_json" IS '원본 JSON 데이터';

COMMENT ON TABLE "upbit_rsi" IS 'RSI 계산 결과 테이블';

COMMENT ON COLUMN "upbit_rsi"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_rsi"."market" IS '마켓 코드 FK';

COMMENT ON COLUMN "upbit_rsi"."candle_date_time_utc" IS 'RSI 기준 시점 (캔들 UTC)';

COMMENT ON COLUMN "upbit_rsi"."period" IS 'RSI 계산 기간 (일/분 단위)';

COMMENT ON COLUMN "upbit_rsi"."au" IS 'Average Up (평균 상승폭)';

COMMENT ON COLUMN "upbit_rsi"."ad" IS 'Average Down (평균 하락폭)';

COMMENT ON COLUMN "upbit_rsi"."rs" IS 'RS = AU / AD';

COMMENT ON COLUMN "upbit_rsi"."rsi" IS 'RSI (0~100) 값';

COMMENT ON COLUMN "upbit_rsi"."calculated_at" IS '계산 완료 시각';

COMMENT ON TABLE "upbit_indicators" IS 'Upbit 기술지표 통합 테이블 (EMA, MACD, RSI, ATR, Bollinger 등)';

COMMENT ON COLUMN "upbit_indicators"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_indicators"."market" IS '마켓 코드 FK';

COMMENT ON COLUMN "upbit_indicators"."candle_date_time_utc" IS '지표 계산 기준 시각 (UTC)';

COMMENT ON COLUMN "upbit_indicators"."interval" IS '지표 계산 주기 (예: minute3, day 등)';

COMMENT ON COLUMN "upbit_indicators"."ema12" IS 'EMA(12)';

COMMENT ON COLUMN "upbit_indicators"."ema26" IS 'EMA(26)';

COMMENT ON COLUMN "upbit_indicators"."macd" IS 'MACD 지표 값';

COMMENT ON COLUMN "upbit_indicators"."macd_signal" IS 'MACD 시그널 라인';

COMMENT ON COLUMN "upbit_indicators"."macd_hist" IS 'MACD 히스토그램 값';

COMMENT ON COLUMN "upbit_indicators"."rsi14" IS 'RSI(14)';

COMMENT ON COLUMN "upbit_indicators"."atr14" IS 'ATR(14) 평균진폭';

COMMENT ON COLUMN "upbit_indicators"."bb_upper" IS '볼린저밴드 상단';

COMMENT ON COLUMN "upbit_indicators"."bb_middle" IS '볼린저밴드 중단 (이동평균선)';

COMMENT ON COLUMN "upbit_indicators"."bb_lower" IS '볼린저밴드 하단';

COMMENT ON COLUMN "upbit_indicators"."calculated_at" IS '지표 계산 시각';

COMMENT ON TABLE "upbit_trades" IS 'Upbit 체결 데이터 (/trades/ticks API)';

COMMENT ON COLUMN "upbit_trades"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_trades"."market" IS '마켓 코드 FK';

COMMENT ON COLUMN "upbit_trades"."trade_timestamp" IS 'Unix timestamp(ms) 기준 체결 시각';

COMMENT ON COLUMN "upbit_trades"."trade_date_time_utc" IS 'UTC 변환 체결 시각';

COMMENT ON COLUMN "upbit_trades"."trade_price" IS '체결 가격';

COMMENT ON COLUMN "upbit_trades"."trade_volume" IS '체결 수량';

COMMENT ON COLUMN "upbit_trades"."ask_bid" IS '매수(BID) 또는 매도(ASK) 구분';

COMMENT ON COLUMN "upbit_trades"."prev_closing_price" IS '전일 종가';

COMMENT ON COLUMN "upbit_trades"."change" IS '상승/하락/보합 (RISE/FALL/EVEN)';

COMMENT ON COLUMN "upbit_trades"."sequential_id" IS 'Upbit 거래 고유 식별자 (순차 ID)';

COMMENT ON COLUMN "upbit_trades"."collected_at" IS '데이터 수집 시각';

COMMENT ON COLUMN "upbit_trades"."raw_json" IS '원본 JSON 데이터';

COMMENT ON TABLE "upbit_orderbook" IS 'Upbit 호가창 데이터 (/orderbook API)';

COMMENT ON COLUMN "upbit_orderbook"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_orderbook"."market" IS '마켓 코드 FK';

COMMENT ON COLUMN "upbit_orderbook"."timestamp" IS 'Unix timestamp(ms) 기준 호가창 시각';

COMMENT ON COLUMN "upbit_orderbook"."total_ask_size" IS '전체 매도호가 수량 합계';

COMMENT ON COLUMN "upbit_orderbook"."total_bid_size" IS '전체 매수호가 수량 합계';

COMMENT ON COLUMN "upbit_orderbook"."raw_json" IS '전체 호가창 JSON 데이터 (최대 10호가)';

COMMENT ON COLUMN "upbit_orderbook"."collected_at" IS '데이터 수집 시각';

COMMENT ON TABLE "upbit_accounts" IS 'Upbit 보유 자산 정보 (/v1/accounts API)';

COMMENT ON COLUMN "upbit_accounts"."id" IS '내부 식별자 (자동 증가)';

COMMENT ON COLUMN "upbit_accounts"."account_id" IS '계정 식별자 (accounts 테이블 FK 가능)';

COMMENT ON COLUMN "upbit_accounts"."currency" IS '보유 자산 화폐 코드 (예: BTC, KRW)';

COMMENT ON COLUMN "upbit_accounts"."balance" IS '주문 가능 잔고 수량';

COMMENT ON COLUMN "upbit_accounts"."locked" IS '거래/주문 등에 묶여있는 잔고 수량';

COMMENT ON COLUMN "upbit_accounts"."avg_buy_price" IS '평균 매수가격 (평균 단가)';

COMMENT ON COLUMN "upbit_accounts"."avg_buy_price_modified" IS '평균가 수동 수정 여부';

COMMENT ON COLUMN "upbit_accounts"."unit_currency" IS '평균가 기준 통화 (예: KRW)';

COMMENT ON COLUMN "upbit_accounts"."collected_at" IS 'API 응답 수집 시각';

COMMENT ON COLUMN "upbit_accounts"."raw_json" IS '원본 JSON 전체 저장';

