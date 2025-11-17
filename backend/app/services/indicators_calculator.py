"""
기술 지표 계산 모듈
RSI, MACD, EMA, ATR, Bollinger Bands 등의 기술 지표를 계산합니다.
"""

import logging
import math
from typing import List, Dict, Optional, Sequence, Mapping
from decimal import Decimal, ROUND_DOWN
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.database import UpbitDayCandles, UpbitCandlesMinute3, UpbitRSI, UpbitIndicators

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSICalculator:
    """
    RSI (Relative Strength Index) 계산 클래스
    제공된 코드를 참고하여 백엔드 구조에 맞게 구현했습니다.
    """
    
    @staticmethod
    def calculate_rsi(candle_data: Sequence, period: int = 14) -> Mapping:
        """
        RSI 계산 함수
        캔들 데이터를 기반으로 RSI 지표를 계산합니다.
        
        Args:
            candle_data: 캔들 데이터 시퀀스 (최소 period+1개 필요)
            period: RSI 계산 기간 (기본값: 14)
        
        Returns:
            Dict: AU, AD, RS, RSI 값을 포함한 딕셔너리
        
        Raises:
            ValueError: 캔들 데이터가 부족한 경우
        """
        if len(candle_data) < period + 1:
            raise ValueError(
                f"최소 {period + 1}개의 캔들 데이터가 필요합니다. 현재: {len(candle_data)}개"
            )
        
        # 상승폭과 하락폭 계산
        gains = []
        losses = []
        
        for item in candle_data:
            change = item.get('change_price', 0.0)
            if isinstance(change, (int, float)):
                if change > 0:
                    gains.append(change)
                else:
                    gains.append(0.0)
                
                if change < 0:
                    losses.append(abs(change))
                else:
                    losses.append(0.0)
            else:
                # Decimal이나 문자열인 경우 처리
                try:
                    if change:
                        change_val = float(change)
                    else:
                        change_val = 0.0
                    
                    if change_val > 0:
                        gains.append(change_val)
                    else:
                        gains.append(0.0)
                    
                    if change_val < 0:
                        losses.append(abs(change_val))
                    else:
                        losses.append(0.0)
                except (ValueError, TypeError):
                    gains.append(0.0)
                    losses.append(0.0)
        
        # 초기 평균 상승폭(AU)과 평균 하락폭(AD) 계산
        initial_au = sum(gains[:period]) / period
        initial_ad = sum(losses[:period]) / period
        
        au = initial_au
        ad = initial_ad
        
        # 지수 이동평균 방식으로 업데이트
        for i in range(period, len(gains)):
            au = (au * (period - 1) + gains[i]) / period
            ad = (ad * (period - 1) + losses[i]) / period
        
        # RS와 RSI 계산
        if ad == 0:
            rs = float('inf')
            rsi = 100.0  # ad가 0이면 RSI는 100
        else:
            rs = au / ad
            rsi = (100 - 100 / (1 + rs))
        
        # Decimal 변환 시 안전하게 처리
        try:
            au_decimal = Decimal(str(au)).quantize(Decimal("1e-4"), rounding=ROUND_DOWN)
        except Exception:
            au_decimal = Decimal("0.0000")
        
        try:
            ad_decimal = Decimal(str(ad)).quantize(Decimal("1e-4"), rounding=ROUND_DOWN)
        except Exception:
            ad_decimal = Decimal("0.0000")
        
        try:
            if rs == float('inf'):
                rs_decimal = Decimal("9999.9999")
            else:
                rs_decimal = Decimal(str(rs)).quantize(Decimal("1e-4"), rounding=ROUND_DOWN)
        except Exception:
            rs_decimal = Decimal("0.0000")
        
        try:
            rsi_decimal = Decimal(str(rsi)).quantize(Decimal("1e-4"), rounding=ROUND_DOWN)
        except Exception:
            rsi_decimal = Decimal("0.0000")
        
        return {
            "AU": str(au_decimal),
            "AD": str(ad_decimal),
            "RS": str(rs_decimal),
            "RSI": str(rsi_decimal)
        }
    
    @staticmethod
    def prepare_candle_data_for_rsi(candles: List) -> List[Dict]:
        """
        데이터베이스에서 가져온 캔들 데이터를 RSI 계산에 맞는 형식으로 변환
        
        Args:
            candles: 데이터베이스 캔들 객체 리스트 (시간 순서대로 정렬되어 있어야 함)
        
        Returns:
            List[Dict]: RSI 계산에 사용할 수 있는 형식의 데이터
        
        Note:
            RSI 계산은 change_price를 사용합니다.
            change_price는 "trade_price - prev_closing_price"로 계산된 값입니다.
            일봉 데이터는 change_price가 항상 제공되므로 그대로 사용합니다.
        """
        candle_data = []
        
        for candle in candles:
            # change_price 사용 (Upbit API 문서 기준)
            # change_price = trade_price - prev_closing_price
            if candle.change_price is not None:
                change_price = float(candle.change_price)
            else:
                # change_price가 없는 경우 (일봉 데이터는 항상 있음)
                # prev_closing_price와 trade_price로 계산
                if candle.trade_price is not None and candle.prev_closing_price is not None:
                    change_price = float(candle.trade_price) - float(candle.prev_closing_price)
                else:
                    change_price = 0.0
            
            candle_data.append({
                'change_price': change_price,
                'candle_date_time_utc': candle.candle_date_time_utc,
                'market': candle.market
            })
        return candle_data


class EMACalculator:
    """
    EMA (Exponential Moving Average) 계산 클래스
    """
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        """
        EMA 계산 함수
        
        Args:
            prices: 가격 리스트 (종가 사용)
            period: EMA 기간
        
        Returns:
            float: EMA 값
        """
        if len(prices) < period:
            raise ValueError(f"최소 {period}개의 가격 데이터가 필요합니다.")
        
        # 초기 EMA는 SMA(단순 이동평균)로 시작
        sma = sum(prices[:period]) / period
        multiplier = 2 / (period + 1)
        
        ema = sma
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema


class MACDCalculator:
    """
    MACD (Moving Average Convergence Divergence) 계산 클래스
    """
    
    @staticmethod
    def calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Dict:
        """
        MACD 계산 함수
        
        Args:
            prices: 가격 리스트 (종가 사용)
            fast_period: 빠른 EMA 기간 (기본값: 12)
            slow_period: 느린 EMA 기간 (기본값: 26)
            signal_period: 시그널 라인 기간 (기본값: 9)
        
        Returns:
            Dict: MACD, Signal, Histogram 값을 포함한 딕셔너리
        """
        if len(prices) < slow_period + signal_period:
            raise ValueError(f"최소 {slow_period + signal_period}개의 가격 데이터가 필요합니다.")
        
        # EMA 계산
        ema_fast = EMACalculator.calculate_ema(prices, fast_period)
        ema_slow = EMACalculator.calculate_ema(prices, slow_period)
        
        # MACD 라인 = EMA(12) - EMA(26)
        macd_line = ema_fast - ema_slow
        
        # MACD 라인 값들을 수집하여 시그널 라인 계산
        # 실제로는 각 시점의 MACD 값을 계산해야 하지만, 
        # 여기서는 최종 MACD 값만 사용하여 근사치 계산
        macd_values = []
        for i in range(slow_period, len(prices)):
            fast_ema = EMACalculator.calculate_ema(prices[:i+1], fast_period)
            slow_ema = EMACalculator.calculate_ema(prices[:i+1], slow_period)
            macd_values.append(fast_ema - slow_ema)
        
        # 시그널 라인 계산 (MACD의 EMA)
        if len(macd_values) >= signal_period:
            signal_line = EMACalculator.calculate_ema(macd_values, signal_period)
        else:
            signal_line = macd_line
        
        # 히스토그램 = MACD - Signal
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }


class ATRCalculator:
    """
    ATR (Average True Range) 계산 클래스
    """
    
    @staticmethod
    def calculate_atr(candles: List, period: int = 14) -> float:
        """
        ATR 계산 함수
        
        Args:
            candles: 캔들 데이터 리스트 (high, low, close 포함)
            period: ATR 기간 (기본값: 14)
        
        Returns:
            float: ATR 값
        """
        if len(candles) < period + 1:
            raise ValueError(f"최소 {period + 1}개의 캔들 데이터가 필요합니다.")
        
        true_ranges = []
        
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i-1]
            
            high = float(current.get('high_price', current.get('trade_price', 0)))
            low = float(current.get('low_price', current.get('trade_price', 0)))
            prev_close = float(previous.get('trade_price', previous.get('close', 0)))
            
            # True Range 계산
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        # 초기 ATR은 True Range의 평균
        initial_atr = sum(true_ranges[:period]) / period
        
        # 지수 이동평균 방식으로 업데이트
        atr = initial_atr
        for tr in true_ranges[period:]:
            atr = (atr * (period - 1) + tr) / period
        
        return atr


class BollingerBandsCalculator:
    """
    Bollinger Bands 계산 클래스
    """
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, num_std: float = 2.0) -> Dict:
        """
        Bollinger Bands 계산 함수
        
        Args:
            prices: 가격 리스트 (종가 사용)
            period: 이동평균 기간 (기본값: 20)
            num_std: 표준편차 배수 (기본값: 2.0)
        
        Returns:
            Dict: 상단, 중단, 하단 밴드 값을 포함한 딕셔너리
        """
        if len(prices) < period:
            raise ValueError(f"최소 {period}개의 가격 데이터가 필요합니다.")
        
        # 최근 period개의 가격 사용
        recent_prices = prices[-period:]
        
        # 중간 밴드 (SMA)
        middle_band = sum(recent_prices) / period
        
        # 표준편차 계산
        variance = sum((x - middle_band) ** 2 for x in recent_prices) / period
        std_dev = math.sqrt(variance)
        
        # 상단 및 하단 밴드
        upper_band = middle_band + (num_std * std_dev)
        lower_band = middle_band - (num_std * std_dev)
        
        return {
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band
        }


class IndicatorsCalculator:
    """
    기술 지표 계산 통합 클래스
    RSI, MACD, EMA, ATR, Bollinger Bands 등 다양한 지표를 계산합니다.
    """
    
    @staticmethod
    def prepare_candle_data_for_indicators(candles: List) -> Dict:
        """
        데이터베이스에서 가져온 캔들 데이터를 지표 계산에 맞는 형식으로 변환
        
        Args:
            candles: 데이터베이스 캔들 객체 리스트
        
        Returns:
            Dict: 지표 계산에 사용할 수 있는 형식의 데이터
        """
        prices = []
        candle_list = []
        
        for candle in candles:
            if candle.trade_price is not None:
                close_price = float(candle.trade_price)
            else:
                close_price = 0.0
            
            if candle.high_price is not None:
                high_price = float(candle.high_price)
            else:
                high_price = close_price
            
            if candle.low_price is not None:
                low_price = float(candle.low_price)
            else:
                low_price = close_price
            
            if candle.opening_price is not None:
                open_price = float(candle.opening_price)
            else:
                open_price = close_price
            
            prices.append(close_price)
            candle_list.append({
                'high_price': high_price,
                'low_price': low_price,
                'trade_price': close_price,
                'opening_price': open_price
            })
        
        return {
            'prices': prices,
            'candles': candle_list
        }
    
    @staticmethod
    def calculate_all_indicators(
        db: Session,
        market: str,
        use_day_candles: bool = True,
        count: Optional[int] = None
    ) -> Optional[Dict]:
        """
        모든 기술 지표를 계산하고 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            market: 마켓 코드
            use_day_candles: True면 일봉 사용, False면 3분봉 사용
            count: 사용할 캔들 개수
        
        Returns:
            Dict: 계산된 모든 지표 데이터 또는 None
        """
        try:
            # count가 None이면 기본값 사용
            if count is None:
                from app.core.config import ScriptConfig
                count = ScriptConfig.DEFAULT_INDICATORS_CANDLE_COUNT
            
            # 최소 필요한 데이터 개수 계산
            # EMA(50)은 최소 50개, MACD는 최소 35개(26+9) 필요
            # 따라서 최소 50개 이상 필요
            min_required_count = max(50, count)  # EMA(50)을 위해 최소 50개 필요
            
            # 캔들 데이터 조회 (최신 데이터부터 가져와서 오래된 순서로 정렬)
            if use_day_candles:
                candles = db.query(UpbitDayCandles).filter(
                    UpbitDayCandles.market == market
                ).order_by(UpbitDayCandles.candle_date_time_utc.desc()).limit(min_required_count).all()
                # 오래된 것부터 정렬 (지표 계산을 위해 시간 순서 필요)
                candles = list(reversed(candles))
            else:
                candles = db.query(UpbitCandlesMinute3).filter(
                    UpbitCandlesMinute3.market == market
                ).order_by(UpbitCandlesMinute3.candle_date_time_utc.desc()).limit(min_required_count).all()
                # 오래된 것부터 정렬 (지표 계산을 위해 시간 순서 필요)
                candles = list(reversed(candles))
            
            # 실제로 가져온 데이터가 충분한지 확인
            if len(candles) < 50:  # EMA(50) 계산을 위해 최소 50개 필요
                logger.warning(f"⚠️ {market} 지표 계산: 데이터 부족 ({len(candles)}개 < 50개 필요, EMA(50) 및 MACD 계산 불가)")
                return None
            
            # count가 지정된 경우, 최신 count개만 사용 (슬라이딩 윈도우)
            if count is not None and len(candles) > count:
                candles = candles[-count:]
            
            # 캔들 데이터 변환
            data = IndicatorsCalculator.prepare_candle_data_for_indicators(candles)
            prices = data['prices']
            candle_list = data['candles']
            
            # 각 지표 계산
            indicators = {}
            
            # EMA 계산
            try:
                ema12 = EMACalculator.calculate_ema(prices, 12)
                ema26 = EMACalculator.calculate_ema(prices, 26)
                indicators['ema12'] = ema12
                indicators['ema26'] = ema26
            except Exception as e:
                logger.warning(f"⚠️ {market} EMA 계산 실패: {e}")
                indicators['ema12'] = None
                indicators['ema26'] = None
            
            # EMA(20) 계산
            try:
                ema20 = EMACalculator.calculate_ema(prices, 20)
                indicators['ema20'] = ema20
            except Exception as e:
                logger.warning(f"⚠️ {market} EMA(20) 계산 실패: {e}")
                indicators['ema20'] = None
            
            # EMA(50) 계산
            try:
                ema50 = EMACalculator.calculate_ema(prices, 50)
                indicators['ema50'] = ema50
            except Exception as e:
                logger.warning(f"⚠️ {market} EMA(50) 계산 실패: {e}")
                indicators['ema50'] = None
            
            # MACD 계산
            try:
                macd_data = MACDCalculator.calculate_macd(prices, 12, 26, 9)
                indicators['macd'] = macd_data['macd']
                indicators['macd_signal'] = macd_data['signal']
                indicators['macd_hist'] = macd_data['histogram']
            except Exception as e:
                logger.warning(f"⚠️ {market} MACD 계산 실패: {e}")
                indicators['macd'] = None
                indicators['macd_signal'] = None
                indicators['macd_hist'] = None
            
            # RSI(14) 계산
            try:
                candle_data = RSICalculator.prepare_candle_data_for_rsi(candles)
                rsi_data = RSICalculator.calculate_rsi(candle_data, 14)
                indicators['rsi14'] = float(rsi_data['RSI'])
            except Exception as e:
                logger.warning(f"⚠️ {market} RSI(14) 계산 실패: {e}")
                indicators['rsi14'] = None
            
            # RSI(7) 계산
            rsi7_data = None
            try:
                rsi7_data = RSICalculator.calculate_rsi(candle_data, 7)
                indicators['rsi7'] = float(rsi7_data['RSI'])
            except Exception as e:
                logger.warning(f"⚠️ {market} RSI(7) 계산 실패: {e}")
                indicators['rsi7'] = None
                rsi7_data = None
            
            # ATR(14) 계산
            try:
                atr14 = ATRCalculator.calculate_atr(candle_list, 14)
                indicators['atr14'] = atr14
            except Exception as e:
                logger.warning(f"⚠️ {market} ATR(14) 계산 실패: {e}")
                indicators['atr14'] = None
            
            # ATR(3) 계산
            try:
                atr3 = ATRCalculator.calculate_atr(candle_list, 3)
                indicators['atr3'] = atr3
            except Exception as e:
                logger.warning(f"⚠️ {market} ATR(3) 계산 실패: {e}")
                indicators['atr3'] = None
            
            # Bollinger Bands 계산
            try:
                bb_data = BollingerBandsCalculator.calculate_bollinger_bands(prices, 20, 2.0)
                indicators['bb_upper'] = bb_data['upper']
                indicators['bb_middle'] = bb_data['middle']
                indicators['bb_lower'] = bb_data['lower']
            except Exception as e:
                logger.warning(f"⚠️ {market} Bollinger Bands 계산 실패: {e}")
                indicators['bb_upper'] = None
                indicators['bb_middle'] = None
                indicators['bb_lower'] = None
            
            # 가장 최근 캔들의 시각 사용
            latest_candle = candles[-1]
            candle_date_time_utc = latest_candle.candle_date_time_utc
            
            # interval 값 결정
            interval = 'day' if use_day_candles else 'minute3'
            
            # RSI(7) 저장 (upbit_rsi 테이블)
            if rsi7_data is not None:
                try:
                    # 중복 체크 (UNIQUE INDEX: market, candle_date_time_utc, period, interval)
                    existing_rsi7 = db.query(UpbitRSI).filter(
                        UpbitRSI.market == market,
                        UpbitRSI.candle_date_time_utc == candle_date_time_utc,
                        UpbitRSI.period == 7,
                        UpbitRSI.interval == interval
                    ).first()
                    
                    if not existing_rsi7:
                        # Null 값 체크
                        null_fields = []
                        if rsi7_data.get("AU") is None:
                            null_fields.append("AU")
                        if rsi7_data.get("AD") is None:
                            null_fields.append("AD")
                        if rsi7_data.get("RS") is None:
                            null_fields.append("RS")
                        if rsi7_data.get("RSI") is None:
                            null_fields.append("RSI")
                        
                        if null_fields:
                            logger.debug(f"⚠️ {market} RSI(7, interval={interval}) Null 값 발견: {', '.join(null_fields)}")
                        
                        rsi7_obj = UpbitRSI(
                            market=market,
                            candle_date_time_utc=candle_date_time_utc,
                            interval=interval,
                            period=7,
                            au=Decimal(rsi7_data["AU"]) if rsi7_data.get("AU") is not None else None,
                            ad=Decimal(rsi7_data["AD"]) if rsi7_data.get("AD") is not None else None,
                            rs=Decimal(rsi7_data["RS"]) if rsi7_data.get("RS") is not None else None,
                            rsi=Decimal(rsi7_data["RSI"]) if rsi7_data.get("RSI") is not None else None
                        )
                        db.add(rsi7_obj)
                        db.commit()
                        logger.debug(f"✅ {market} RSI(7) 저장 완료 (RSI={rsi7_data.get('RSI', 'None')})")
                    else:
                        logger.debug(f"⏭️ {market} RSI(7) 이미 존재 (건너뜀)")
                except Exception as e:
                    logger.warning(f"⚠️ {market} RSI(7) 저장 실패: {e}")
                    db.rollback()
            
            # upbit_indicators 테이블에 저장
            # 중복 체크 (UNIQUE INDEX: market, candle_date_time_utc, interval)
            existing_indicator = db.query(UpbitIndicators).filter(
                UpbitIndicators.market == market,
                UpbitIndicators.candle_date_time_utc == candle_date_time_utc,
                UpbitIndicators.interval == interval
            ).first()
            
            if not existing_indicator:
                # Null 값 체크 및 디버그 로그
                null_fields = []
                
                ema12_value = None
                if indicators['ema12'] is not None:
                    ema12_value = Decimal(str(indicators['ema12']))
                else:
                    null_fields.append("ema12")
                
                ema20_value = None
                if indicators['ema20'] is not None:
                    ema20_value = Decimal(str(indicators['ema20']))
                else:
                    null_fields.append("ema20")
                
                ema26_value = None
                if indicators['ema26'] is not None:
                    ema26_value = Decimal(str(indicators['ema26']))
                else:
                    null_fields.append("ema26")
                
                ema50_value = None
                if indicators['ema50'] is not None:
                    ema50_value = Decimal(str(indicators['ema50']))
                else:
                    null_fields.append("ema50")
                
                macd_value = None
                if indicators['macd'] is not None:
                    macd_value = Decimal(str(indicators['macd']))
                else:
                    null_fields.append("macd")
                
                macd_signal_value = None
                if indicators['macd_signal'] is not None:
                    macd_signal_value = Decimal(str(indicators['macd_signal']))
                else:
                    null_fields.append("macd_signal")
                
                macd_hist_value = None
                if indicators['macd_hist'] is not None:
                    macd_hist_value = Decimal(str(indicators['macd_hist']))
                else:
                    null_fields.append("macd_hist")
                
                rsi14_value = None
                if indicators['rsi14'] is not None:
                    rsi14_value = Decimal(str(indicators['rsi14']))
                else:
                    null_fields.append("rsi14")
                
                atr3_value = None
                if indicators['atr3'] is not None:
                    atr3_value = Decimal(str(indicators['atr3']))
                else:
                    null_fields.append("atr3")
                
                atr14_value = None
                if indicators['atr14'] is not None:
                    atr14_value = Decimal(str(indicators['atr14']))
                else:
                    null_fields.append("atr14")
                
                bb_upper_value = None
                if indicators['bb_upper'] is not None:
                    bb_upper_value = Decimal(str(indicators['bb_upper']))
                else:
                    null_fields.append("bb_upper")
                
                bb_middle_value = None
                if indicators['bb_middle'] is not None:
                    bb_middle_value = Decimal(str(indicators['bb_middle']))
                else:
                    null_fields.append("bb_middle")
                
                bb_lower_value = None
                if indicators['bb_lower'] is not None:
                    bb_lower_value = Decimal(str(indicators['bb_lower']))
                else:
                    null_fields.append("bb_lower")
                
                if null_fields:
                    logger.debug(f"⚠️ {market} 통합 지표 Null 값 발견: {', '.join(null_fields)}")
                
                indicator_obj = UpbitIndicators(
                    market=market,
                    candle_date_time_utc=candle_date_time_utc,
                    interval=interval,
                    ema12=ema12_value,
                    ema20=ema20_value,
                    ema26=ema26_value,
                    ema50=ema50_value,
                    macd=macd_value,
                    macd_signal=macd_signal_value,
                    macd_hist=macd_hist_value,
                    rsi14=rsi14_value,
                    atr3=atr3_value,
                    atr14=atr14_value,
                    bb_upper=bb_upper_value,
                    bb_middle=bb_middle_value,
                    bb_lower=bb_lower_value
                )
                db.add(indicator_obj)
                db.commit()
                logger.debug(f"✅ {market} 통합 지표 저장 완료")
            else:
                logger.debug(f"⏭️ {market} 통합 지표 이미 존재 (건너뜀)")
            
            candle_date_time_utc_str = None
            if candle_date_time_utc is not None:
                candle_date_time_utc_str = candle_date_time_utc.isoformat()
            
            return {
                "market": market,
                "candle_date_time_utc": candle_date_time_utc_str,
                **indicators
            }
        
        except Exception as e:
            logger.error(f"❌ {market} 통합 지표 계산 오류: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def calculate_and_save_rsi(
        db: Session,
        market: str,
        period: int = 14,
        use_day_candles: bool = True,
        count: Optional[int] = None
    ) -> Optional[Dict]:
        """
        RSI를 계산하고 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            market: 마켓 코드
            period: RSI 계산 기간
            use_day_candles: True면 일봉 사용, False면 3분봉 사용
            count: 사용할 캔들 개수
        
        Returns:
            Dict: 계산된 RSI 데이터 또는 None
        """
        try:
            # count가 None이면 기본값 사용
            if count is None:
                from app.core.config import ScriptConfig
                count = ScriptConfig.DEFAULT_INDICATORS_CANDLE_COUNT
            
            # 캔들 데이터 조회 (최신 데이터부터 가져와서 오래된 순서로 정렬)
            if use_day_candles:
                candles = db.query(UpbitDayCandles).filter(
                    UpbitDayCandles.market == market
                ).order_by(UpbitDayCandles.candle_date_time_utc.desc()).limit(count).all()
                # 오래된 것부터 정렬 (지표 계산을 위해 시간 순서 필요)
                candles = list(reversed(candles))
            else:
                candles = db.query(UpbitCandlesMinute3).filter(
                    UpbitCandlesMinute3.market == market
                ).order_by(UpbitCandlesMinute3.candle_date_time_utc.desc()).limit(count).all()
                # 오래된 것부터 정렬 (지표 계산을 위해 시간 순서 필요)
                candles = list(reversed(candles))
            
            if len(candles) < period + 1:
                logger.warning(f"⚠️ {market} RSI 계산: 데이터 부족 ({len(candles)}개 < {period + 1}개 필요)")
                return None
            
            # 캔들 데이터 변환
            candle_data = RSICalculator.prepare_candle_data_for_rsi(candles)
            
            # RSI 계산
            rsi_data = RSICalculator.calculate_rsi(candle_data, period)
            
            # 가장 최근 캔들의 시각 사용
            latest_candle = candles[-1]
            candle_date_time_utc = latest_candle.candle_date_time_utc
            
            # interval 값 결정
            interval = 'day' if use_day_candles else 'minute3'
            
            # upbit_rsi 테이블에 저장
            # 중복 체크 (UNIQUE INDEX: market, candle_date_time_utc, period, interval)
            existing_rsi = db.query(UpbitRSI).filter(
                UpbitRSI.market == market,
                UpbitRSI.candle_date_time_utc == candle_date_time_utc,
                UpbitRSI.period == period,
                UpbitRSI.interval == interval
            ).first()
            
            if not existing_rsi:
                # Null 값 체크
                null_fields = []
                if rsi_data.get("AU") is None:
                    null_fields.append("AU")
                if rsi_data.get("AD") is None:
                    null_fields.append("AD")
                if rsi_data.get("RS") is None:
                    null_fields.append("RS")
                if rsi_data.get("RSI") is None:
                    null_fields.append("RSI")
                
                if null_fields:
                    logger.debug(f"⚠️ {market} RSI(period={period}, interval={interval}) Null 값 발견: {', '.join(null_fields)}")
                
                rsi_obj = UpbitRSI(
                    market=market,
                    candle_date_time_utc=candle_date_time_utc,
                    interval=interval,
                    period=period,
                    au=Decimal(rsi_data["AU"]) if rsi_data.get("AU") is not None else None,
                    ad=Decimal(rsi_data["AD"]) if rsi_data.get("AD") is not None else None,
                    rs=Decimal(rsi_data["RS"]) if rsi_data.get("RS") is not None else None,
                    rsi=Decimal(rsi_data["RSI"]) if rsi_data.get("RSI") is not None else None
                )
                db.add(rsi_obj)
                db.commit()
                logger.debug(f"✅ {market} RSI 저장 완료 (period={period}, interval={interval}, RSI={rsi_data.get('RSI', 'None')})")
            else:
                logger.debug(f"⏭️ {market} RSI 이미 존재 (건너뜀, period={period})")
            
            # upbit_indicators 테이블에도 저장 (통합 지표 테이블)
            interval = "day" if use_day_candles else "minute3"
            existing_indicator = db.query(UpbitIndicators).filter(
                UpbitIndicators.market == market,
                UpbitIndicators.candle_date_time_utc == candle_date_time_utc,
                UpbitIndicators.interval == interval
            ).first()
            
            if not existing_indicator:
                indicator_obj = UpbitIndicators(
                    market=market,
                    candle_date_time_utc=candle_date_time_utc,
                    interval=interval,
                    rsi14=Decimal(rsi_data["RSI"])
                )
                db.add(indicator_obj)
                db.commit()
                logger.debug(f"✅ {market} indicators 테이블에 RSI(14) 저장 완료")
            else:
                logger.debug(f"⏭️ {market} indicators 이미 존재 (건너뜀, interval={interval})")
            
            return {
                "market": market,
                "period": period,
                "rsi": float(rsi_data["RSI"]),
                "au": float(rsi_data["AU"]),
                "ad": float(rsi_data["AD"]),
                "rs": float(rsi_data["RS"]),
                "candle_date_time_utc": candle_date_time_utc.isoformat() if candle_date_time_utc else None
            }
        
        except Exception as e:
            logger.error(f"❌ {market} RSI 계산 오류: {e}")
            db.rollback()
            return None
    
    @staticmethod
    def calculate_rsi_for_all_markets(
        db: Session,
        markets: List[str],
        period: int = 14,
        use_day_candles: bool = True
    ) -> List[Dict]:
        """
        여러 마켓의 RSI를 일괄 계산
        
        Args:
            db: 데이터베이스 세션
            markets: 마켓 코드 리스트
            period: RSI 계산 기간
            use_day_candles: True면 일봉 사용, False면 3분봉 사용
        
        Returns:
            List[Dict]: 계산된 RSI 데이터 리스트
        """
        results = []
        for market in markets:
            result = IndicatorsCalculator.calculate_and_save_rsi(
                db, market, period, use_day_candles
            )
            if result:
                results.append(result)
        return results
    
    @staticmethod
    def calculate_all_indicators_for_markets(
        db: Session,
        markets: List[str],
        use_day_candles: bool = True
    ) -> List[Dict]:
        """
        여러 마켓의 모든 기술 지표를 일괄 계산
        
        Args:
            db: 데이터베이스 세션
            markets: 마켓 코드 리스트
            use_day_candles: True면 일봉 사용, False면 3분봉 사용
        
        Returns:
            List[Dict]: 계산된 모든 지표 데이터 리스트
        """
        results = []
        for market in markets:
            result = IndicatorsCalculator.calculate_all_indicators(
                db, market, use_day_candles
            )
            if result:
                results.append(result)
        return results