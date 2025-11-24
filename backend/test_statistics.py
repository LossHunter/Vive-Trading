"""
통계 함수 테스트 스크립트

이 스크립트는 statistics_service.py에 정의된 모든 통계 함수를 실행하고
결과를 보기 좋게 정리하여 출력합니다.

사용법:
    python test_statistics.py

기능:
    - 모든 통계 함수를 순차적으로 실행
    - 각 함수의 실행 결과를 JSON 형식으로 출력
    - 오류 발생 시 상세한 에러 메시지 출력
    - 결과 데이터가 많을 경우 샘플만 출력하여 가독성 향상

주의사항:
    - 데이터베이스 연결이 필요합니다
    - Docker 환경에서 실행 시 DB_HOST가 "db"로 설정되어 있어야 합니다
    - 로컬에서 실행 시 .env 파일의 DB 설정을 확인하세요
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.db.database import SessionLocal
from app.services.statistics_service import (
    get_balance_change_statistics,
    get_coin_profit_statistics,
    get_model_profit_comparison,
    get_stop_loss_profit_target_achievement,
    get_total_asset_trend,
    get_coin_holdings_distribution,
    get_hourly_asset_changes,
    get_model_asset_comparison,
    get_max_profit_loss,
    get_stop_loss_achievement_rate,
    get_profit_target_achievement_rate,
    get_model_avg_profit_rate,
    get_model_confidence_distribution,
    get_model_preferred_coins,
    get_indicator_profit_correlation,
)

# 로깅 설정: INFO 레벨로 설정하여 함수 실행 정보와 오류 메시지 출력
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """
    섹션 구분선을 출력하는 헬퍼 함수
    
    Args:
        title: 섹션 제목
    """
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(function_name: str, result: any, max_items: int = 5):
    """
    테스트 결과를 보기 좋게 출력하는 함수
    
    Args:
        function_name: 테스트한 함수명
        result: 함수 실행 결과 (리스트, 딕셔너리, 또는 기타 타입)
        max_items: 리스트인 경우 출력할 최대 항목 수 (기본값: 5)
    
    출력 형식:
        - 리스트: 항목 개수와 샘플 데이터 출력
        - 딕셔너리: 전체 데이터를 JSON 형식으로 출력
        - 기타: 타입과 값 출력
    """
    print(f"\n📊 함수: {function_name}")
    print("-" * 80)
    
    if isinstance(result, list):
        print(f"✅ 결과: 리스트 ({len(result)}개 항목)")
        if len(result) > 0:
            print(f"\n📋 샘플 데이터 (최대 {max_items}개):")
            for i, item in enumerate(result[:max_items], 1):
                print(f"  [{i}] {json.dumps(item, indent=2, ensure_ascii=False, default=str)}")
            if len(result) > max_items:
                print(f"  ... 외 {len(result) - max_items}개 항목 생략")
        else:
            print("⚠️  데이터 없음")
    
    elif isinstance(result, dict):
        print(f"✅ 결과: 딕셔너리")
        print(f"\n📋 데이터:")
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    else:
        print(f"✅ 결과: {type(result).__name__}")
        print(f"값: {result}")


def test_all_statistics():
    """
    모든 통계 함수를 순차적으로 테스트하는 메인 함수
    
    처리 과정:
        1. 데이터베이스 세션 생성
        2. 각 통계 함수를 카테고리별로 그룹화하여 실행
        3. 각 함수의 실행 결과를 출력
        4. 오류 발생 시 상세한 에러 메시지 출력
        5. 모든 테스트 완료 후 데이터베이스 세션 종료
    
    테스트 카테고리:
        1. 수익성 통계 (4개 함수)
        2. 자산 통계 (5개 함수)
        3. 리스크 관리 통계 (2개 함수)
        4. 모델별 통계 (3개 함수)
        5. 기술 지표 vs 수익률 상관관계 (2개 함수)
    """
    # 데이터베이스 세션 생성
    db = SessionLocal()
    
    try:
        print_section("통계 함수 테스트 시작")
        
        # ==================== 수익성 통계 ====================
        print_section("1. 수익성 통계")
        
        # 1-1. 거래 전후 잔액 변화 통계
        # 각 거래의 잔액 변화량과 변화율을 계산하여 반환
        try:
            result = get_balance_change_statistics(db)
            print_result("get_balance_change_statistics", result, max_items=3)
        except Exception as e:
            logger.error(f"❌ get_balance_change_statistics 오류: {e}", exc_info=True)
        
        # 1-2. 코인별 수익률 통계
        # 각 코인별로 총 거래 횟수, 총 수익, 평균 수익을 집계
        try:
            result = get_coin_profit_statistics(db)
            print_result("get_coin_profit_statistics", result)
        except Exception as e:
            logger.error(f"❌ get_coin_profit_statistics 오류: {e}", exc_info=True)
        
        # 1-3. 모델별 수익률 비교
        # 각 LLM 모델별로 총 거래 횟수, 총 수익, 평균 수익을 집계하여 비교
        try:
            result = get_model_profit_comparison(db)
            print_result("get_model_profit_comparison", result)
        except Exception as e:
            logger.error(f"❌ get_model_profit_comparison 오류: {e}", exc_info=True)
        
        # 1-4. 손절/익절 달성률 통계
        # 설정한 손절가와 익절가가 실제로 달성되었는지 확인하여 달성률 계산
        try:
            result = get_stop_loss_profit_target_achievement(db)
            print_result("get_stop_loss_profit_target_achievement", result)
        except Exception as e:
            logger.error(f"❌ get_stop_loss_profit_target_achievement 오류: {e}", exc_info=True)
        
        # ==================== 자산 통계 ====================
        print_section("2. 자산 통계")
        
        # 2-1. 총 자산 변화 추이
        # 일정 기간 동안의 자산 변화를 시간순으로 조회 (최근 7일)
        try:
            result = get_total_asset_trend(db, days=7)
            print_result("get_total_asset_trend (최근 7일)", result, max_items=3)
        except Exception as e:
            logger.error(f"❌ get_total_asset_trend 오류: {e}", exc_info=True)
        
        # 2-2. 코인별 보유 비중
        # 특정 시점에서 각 계정이 보유한 코인별 자산 비중 계산
        try:
            result = get_coin_holdings_distribution(db)
            print_result("get_coin_holdings_distribution", result)
        except Exception as e:
            logger.error(f"❌ get_coin_holdings_distribution 오류: {e}", exc_info=True)
        
        # 2-3. 시간대별 자산 변화
        # 시간 단위로 그룹화하여 각 시간대별 최대, 최소, 평균 자산 계산 (최근 3일)
        try:
            result = get_hourly_asset_changes(db, days=3)
            print_result("get_hourly_asset_changes (최근 3일)", result, max_items=3)
        except Exception as e:
            logger.error(f"❌ get_hourly_asset_changes 오류: {e}", exc_info=True)
        
        # 2-4. 모델별 자산 비교
        # 특정 시점에서 각 모델의 최신 자산 정보를 조회하여 비교
        try:
            result = get_model_asset_comparison(db)
            print_result("get_model_asset_comparison", result)
        except Exception as e:
            logger.error(f"❌ get_model_asset_comparison 오류: {e}", exc_info=True)
        
        # 2-5. 최대 수익/손실
        # 성공한 거래 중에서 가장 큰 수익과 가장 큰 손실을 찾아 반환
        try:
            result = get_max_profit_loss(db)
            print_result("get_max_profit_loss", result)
        except Exception as e:
            logger.error(f"❌ get_max_profit_loss 오류: {e}", exc_info=True)
        
        # ==================== 리스크 관리 통계 ====================
        print_section("3. 리스크 관리 통계")
        
        # 3-1. 손절가 달성률
        # 설정한 손절가가 실제로 달성되었는지 확인하여 달성률 계산
        try:
            result = get_stop_loss_achievement_rate(db)
            print_result("get_stop_loss_achievement_rate", result)
        except Exception as e:
            logger.error(f"❌ get_stop_loss_achievement_rate 오류: {e}", exc_info=True)
        
        # 3-2. 익절가 달성률
        # 설정한 익절가가 실제로 달성되었는지 확인하여 달성률 계산
        try:
            result = get_profit_target_achievement_rate(db)
            print_result("get_profit_target_achievement_rate", result)
        except Exception as e:
            logger.error(f"❌ get_profit_target_achievement_rate 오류: {e}", exc_info=True)
        
        # ==================== 모델별 통계 ====================
        print_section("4. 모델별 통계")
        
        # 4-1. 모델별 평균 수익률
        # 각 LLM 모델별로 평균 수익률을 계산하여 반환
        try:
            result = get_model_avg_profit_rate(db)
            print_result("get_model_avg_profit_rate", result)
        except Exception as e:
            logger.error(f"❌ get_model_avg_profit_rate 오류: {e}", exc_info=True)
        
        # 4-2. 모델별 신뢰도 분포
        # 각 모델이 거래 신호를 생성할 때 표현한 신뢰도의 통계적 분포 계산
        try:
            result = get_model_confidence_distribution(db)
            print_result("get_model_confidence_distribution", result)
        except Exception as e:
            logger.error(f"❌ get_model_confidence_distribution 오류: {e}", exc_info=True)
        
        # 4-3. 모델별 선호 코인
        # 각 모델이 어떤 코인에 대해 거래 신호를 가장 많이 생성했는지 집계
        try:
            result = get_model_preferred_coins(db)
            print_result("get_model_preferred_coins", result, max_items=10)
        except Exception as e:
            logger.error(f"❌ get_model_preferred_coins 오류: {e}", exc_info=True)
        
        # ==================== 기술 지표 vs 수익률 상관관계 ====================
        print_section("5. 기술 지표 vs 수익률 상관관계")
        
        # 5-1. RSI14 vs 수익률
        # 거래 실행 시점의 RSI(14) 값과 해당 거래의 수익률을 매칭하여 분석
        try:
            result = get_indicator_profit_correlation(db, coin="BTC", indicator_type="rsi14")
            print_result("get_indicator_profit_correlation (BTC, RSI14)", result, max_items=5)
        except Exception as e:
            logger.error(f"❌ get_indicator_profit_correlation (RSI14) 오류: {e}", exc_info=True)
        
        # 5-2. MACD vs 수익률
        # 거래 실행 시점의 MACD 값과 해당 거래의 수익률을 매칭하여 분석
        try:
            result = get_indicator_profit_correlation(db, coin="BTC", indicator_type="macd")
            print_result("get_indicator_profit_correlation (BTC, MACD)", result, max_items=5)
        except Exception as e:
            logger.error(f"❌ get_indicator_profit_correlation (MACD) 오류: {e}", exc_info=True)
        
        print_section("통계 함수 테스트 완료")
        
    except Exception as e:
        # 예상치 못한 오류 발생 시 상세한 에러 메시지 출력
        logger.error(f"❌ 테스트 중 오류 발생: {e}", exc_info=True)
    finally:
        # 테스트 완료 후 데이터베이스 세션 종료
        db.close()


if __name__ == "__main__":
    test_all_statistics()

