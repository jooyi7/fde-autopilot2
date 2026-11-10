/**
 * src/ai/reporter.js (Upgraded v4.0 - 20% Structured AI Adapter & 0.1s Deterministic SOP Fallback)
 * - 오직 결정론 코어(80% - evaluateCoreRules)가 확정한 구조화된 JSON 판정 객체만 입력으로 받습니다.
 * - 허용된 권장 모델(Sol-6.1, Terra-5.6, Luna-6, Sol-6.0)만 호출하며, 금지 모델(Astra)은 코드 레벨에서 원천 차단합니다.
 * - API 타임아웃/네트워크 오프라인/에러 발생 시 0.1초 내에 6대 현업 도메인 전용 표준 SOP 리포트를 반환합니다.
 */

export const ALLOWED_MODELS = ["Sol-6.1", "Terra-5.6", "Luna-6", "Sol-6.0"];

export function sanitizeModelName(requestedModel = "Sol-6.1") {
  const m = String(requestedModel || "Sol-6.1").trim();
  if (m.toLowerCase().includes("astra")) {
    return "Sol-6.1"; // Hard guardrail against forbidden model
  }
  return ALLOWED_MODELS.includes(m) ? m : "Sol-6.1";
}

/**
 * 5대 반도체 도메인별 결정론적 표준 SOP 리포트 생성기 (0.1초 즉시 응답 보장)
 */
export function buildDeterministicDomainSopReport(coreOutput, errorContext = null) {
  const domain = coreOutput?.domain || "GENERIC";
  const status = coreOutput?.status || "WARNING";
  const ruleId = coreOutput?.ruleId || "CORE-SOP-DEFAULT";
  const score = coreOutput?.score ?? 50;

  let executiveSummary = "";
  let rootCauseHypotheses = [];
  let recommendedSopActions = [];
  let accountabilityNote =
    "1차 수치/임계치 판정 책임은 결정론 코어(80%, 규칙 ID: " +
    ruleId +
    ")가 보장하며, 본 AI 리포트(20%)는 보조 의사결정 참고 자료입니다. 최종 예외 승인(Override) 권한과 감사 로그(Audit Trail) 책임은 현업 담당자에게 귀속됩니다.";

  if (domain === "OVERLAY") {
    const m = coreOutput.metrics || {};
    const match = coreOutput.chamber_and_scanner_matching || {};
    const samp = coreOutput.smart_sampling_plan || {};
    executiveSummary = `[이천 포토기술팀 APC 판정: ${status}] ${coreOutput.selected_order || 3}차 비선형(HOWA) 및 전공정 박막 스트레스 Feed-forward 보정 결과, 잔차 M3S가 X축 ${m.before_m3s_dx}nm ➔ ${m.after_m3s_dx}nm (${m.improvement_dx_pct}% 개선), Y축 ${m.before_m3s_dy}nm ➔ ${m.after_m3s_dy}nm (${m.improvement_dy_pct}% 개선)로 산출되었습니다. (규칙: ${ruleId})`;
    rootCauseHypotheses = [
      `원인 귀속 진단: ${match.root_cause_attribution || "N/A"} (Chuck 간 편차 ${match.chuck_to_chuck_delta_nm || 0}nm vs Etch 챔버 간 편차 ${match.etch_chamber_delta_nm || 0}nm)`,
      `물리적 10-Parameter 분석: Wafer Translation(${coreOutput.physical_10param_correctables?.wafer_Tx_nm || 0}nm, ${coreOutput.physical_10param_correctables?.wafer_Ty_nm || 0}nm) 및 Wafer Edge 고차 왜곡 성분 집중`,
    ];
    recommendedSopActions = [
      status === "VIOLATION"
        ? "🚨 [즉시 조치] 해당 Lot Photo Rework(PR Strip 후 재노광) 발령 및 오염 의심 스캐너 Chuck 인터록(Hold) 후 PM 점검 호출"
        : status === "WARNING"
        ? "⚠️ [선제 조치] 전공정 Etch 챔버 박막 스트레스 값을 Feed-forward APC 계수에 연동하고 다음 Lot EWMA 오프셋 자동 반영"
        : "✅ [정상 진행] 산출된 APC 보정 계수를 스캐너에 자동 다운로드하고 인라인 후속 공정 정상 진행",
      `🎯 [계측 TAT 최적화] 전체 ${samp.total_shots || 0}개 샷 중 Edge 취약 상위 ${samp.sampled_shots || 0}개 샷만 스마트 샘플링 측정 (계측 TAT ${samp.tat_reduction_pct || 0}% 절감)`,
      `🧭 [최적 장비 라우팅] Queue Time과 Matching Offset 가중 스코어 1순위 스캐너 [${match.optimal_scanner_routing || "DEFAULT"}]로 후속 Lot 배정`,
    ];
  } else if (domain === "MATERIAL") {
    const topV = coreOutput.vendor_rankings?.[0] || {};
    const fp = topV.fingerprint_analysis || {};
    const sub = topV.subtier_4m_audit || {};
    executiveSummary = `[소재품질팀 공급사 변경 검토: ${status}] 최우선 검토 대상 [${topV.vendor_id || "N/A"}]의 종합 리스크 점수는 ${topV.composite_risk_score || 0}점이며, 최종 판정은 [${topV.decision || status}] (권장 발주 배분율: ${topV.recommended_sourcing_share_pct ?? 0}%)입니다. (규칙: ${ruleId})`;
    rootCauseHypotheses = [
      `스펙트럼 지문(Fingerprint) 분석: 기준 스펙트럼 대비 코사인 유사도 ${fp.cosine_similarity ?? 1.0}, 미측정 불순물 피크 편차 ${fp.max_unmeasured_peak_deviation_pct ?? 0}% (${fp.in_spec_excursion_flag ? "In-Spec Excursion 위험 감지" : "파형 정상"})`,
      `하위 공급망(Sub-tier) 4M 계보 감사: Tier-2(${sub.tier2_lot_id}) / Tier-3(${sub.tier3_lot_id}) 무단 변경 여부 = ${sub.unapproved_4m_change_flag ? "적발됨(PCN 미승인)" : "특이사항 없음"}`,
    ];
    recommendedSopActions = [
      status === "VIOLATION"
        ? `🚨 [즉시 반려(REJECT)] 하위 원료사 무단 4M 변경 또는 CoA 스펙 이탈이 확인되었으므로 양산 투입을 전면 차단하고 영향받은 웨이퍼 로트(${(sub.impacted_wafer_lots || []).join(", ") || "해당 로트"})를 즉시 홀드(Hold) 조치`
        : status === "WARNING"
        ? "⚠️ [조건부 시생산(Pilot 15%)] CoA 스펙 내이나 Baseline 대비 평균 이동(Mean Shift) 및 배관 체류 열화 징후가 있으므로 소규모 Pilot Wafer(15% 물량) 선행 검증 후 확대"
        : "✅ [양산 승인(Approve)] Cpk >= 1.33, 스펙트럼 화학 지문 및 HVM 배관 스트레스 모두 기준을 충족하므로 주력 양산 라인(85% 배분) 투입 승인",
    ];
  } else if (domain === "MARKET") {
    const pq = coreOutput.pq_mix_variance_decomposition || {};
    const irs = coreOutput.ir_vs_financials_cross_audit || [];
    const flaggedIr = irs.find((r) => r.red_flag_detected);
    executiveSummary = `[시장전략팀 경쟁사 실적 분석: ${status}] 캘린더 분기(CQ) 및 NRV 재고평가환입 보정 완료. 전사 Blended ASP 변동(${pq.blended_asp_change_pct || 0}%) 대비 레거시 범용 단가 변동(${pq.legacy_commodity_asp_change_pct || 0}%) 분해 결과, Mix 착시 여부는 [${pq.mix_illusion_flag ? "감지됨(주의)" : "없음"}]입니다. (규칙: ${ruleId})`;
    rootCauseHypotheses = [
      `P×Q×Mix 매출 변동 분해(총 ${pq.total_revenue_variance_musd || 0} MUSD): 물량 효과(${pq.variance_breakdown_musd?.delta_volume_effect || 0}) / 순수 단가 효과(${pq.variance_breakdown_musd?.delta_pure_price_effect || 0}) / HBM 고부가 믹스 효과(+${pq.variance_breakdown_musd?.delta_specialty_mix_effect || 0} MUSD)`,
      flaggedIr
        ? `어닝콜 IR 발언 vs 재무 선행지표 모순 적발: [${flaggedIr.company}] 긍정 발언에도 불구하고 DIO 재고일수 +${flaggedIr.dio_change_days}일 급증 (${flaggedIr.contradiction_codes.join(", ")})`
        : "어닝콜 IR 가이던스와 재고일수(DIO)·CAPEX 집행률 간 정합성 양호",
    ];
    recommendedSopActions = [
      pq.mix_illusion_flag
        ? "⚠️ [가격 착시 방어] 전사 Blended ASP 상승은 HBM3E 비중 확대에 기인한 착시이며 범용 DDR4/구형 NAND 단가는 하락 중이므로, 범용 라인 감산 기조 유지 및 선단 1b/1c 전환 가속화 권고"
        : "✅ [포트폴리오 유지] 고부가 HBM 및 서버용 DDR5 중심의 우호적 가격 환경이 지속되므로 수익성 중심 수주 전략 유지",
      flaggedIr
        ? `🚨 [경쟁사 밀어내기 경보] ${flaggedIr.company}의 재고일수(DIO) 급증 및 매출채권 회전일수 악화는 하반기 레거시 물량 덤핑(Channel Stuffing) 선행 시그널이므로 장기공급계약(LTA) 단가 방어 조항 점검 필수`
        : "📊 [분기 벤치마크 확정] Calendarized CQ 기준 경쟁사 Underlying OPM 비교표를 경영진 주간 회의 자료로 배포",
    ];
  } else if (domain === "VALUE_CHAIN") {
    const vc = coreOutput.value_chain_and_bullwhip_analysis || {};
    const roic = coreOutput.capex_roic_optimization || {};
    executiveSummary = `[경영전략팀 밸류체인 분석(value-chain-business-persona): ${status}] 전방 CSP 수요 충격이 16개월 장비 리드타임을 거치며 상류 장비 발주 변동폭 ${vc.upstream_equipment_order_swing_pct || 0}%로 증폭(Bullwhip)되었습니다. 현재 실질 출하 상한선(Ceiling)은 [${vc.binding_bottleneck_node}]에 의해 ${vc.effective_shippable_ceiling_bgb} B_Gb로 제약됩니다.`;
    rootCauseHypotheses = [
      `생태계 병목 진단: 내부 양품 다이(KGHD) 생산 가능량(${vc.internal_good_die_output_bgb} B_Gb) 대비 외부 패키징/베이스다이 한도로 인해 미출하 좌초 재고 ${vc.stranded_unshipped_die_inventory_bgb} B_Gb (보유 손실 약 ${vc.stranded_holding_loss_musd} MUSD) 발생`,
      `자본 효율성(ROIC vs WACC): 공정 전환 손실(Conversion Loss)과 고객사 LTA 의무 물량을 반영한 포트폴리오 가중 ROIC는 ${roic.portfolio_weighted_roic_pct}% (WACC ${roic.wacc_hurdle_pct}% 대비 EVA +${roic.value_created_eva_musd} MUSD 창출)`,
    ];
    recommendedSopActions = [
      vc.stranded_unshipped_die_inventory_bgb > 0
        ? "⚠️ [패키징 병목 해소 & Wafer-In 속도 조절] 외부 파운드리 CoWoS 할당량 및 OSAT 듀얼 소싱이 확보되기 전까지 초과 전공정 Wafer-In 투입을 조절하여 미출하 KGHD 재고 묶임 방지"
        : "✅ [가치사슬 균형 달성] 내부 Fab 수율과 외부 패키징 캐파가 동기화되어 있으므로 HBM3E 12H/HBM4 램프업 계획 정상 집행",
      "🛡️ [지정학 컨틴전시] 대중국 선단 장비 반입 제한 시나리오 발동 시 우시 Fab은 레거시 캐시카우 공정으로 전환하고 이천 M16/청주 M15X에 1b/1c 및 TSV 투자를 집중",
    ];
  } else if (domain === "EDUCATOR") {
    const misc = coreOutput.misconception_diagnostics || [];
    executiveSummary = `[반도체 산업교육(value-chain-educator-persona): ${status}] 선수과목 위상정렬(Kahn DAG) 검증 결과 ${coreOutput.is_valid_dag ? "순환 참조 없음(정상)" : `순환 참조 오류 적발(${coreOutput.cycle_detected_ids.join(", ")})`}이며, 총 ${coreOutput.learning_path?.length || 0}개 과목(${coreOutput.total_scheduled_hours}시간 / 예산 ${coreOutput.budget_max_hours}시간) 커리큘럼이 생성되었습니다.`;
    rootCauseHypotheses = [
      coreOutput.deferred_modules?.length > 0
        ? `학습 시간 상한(${coreOutput.budget_max_hours}h) 제약으로 인해 핵심 목표 과목은 압축 이수(Fast-Track)로 보존하고 부가 과목 ${coreOutput.deferred_modules.length}건을 차기 차수로 이연함`
        : "모든 필수 선수과목과 최종 목표 과목이 시간 예산 내에 정식 과정(Full Standard)으로 편성됨",
      misc.length > 0
        ? `교육생 오개념 자동 검출(${misc.length}건): ${misc.map((m) => `${m.code}(${m.fix})`).join(" / ")}`
        : "교육생 사전 질의 내 치명적 물리·비즈니스 오개념 없음",
    ];
    recommendedSopActions = [
      !coreOutput.is_valid_dag
        ? `🚨 [커리큘럼 그래프 수정 필수] ${coreOutput.cycle_detected_ids.join(" ↔ ")} 과목 간 상호 선수 지정(Cycle)을 해제하여 진입차수(In-degree) 0인 기초 과목부터 시작하도록 재설계`
        : "✅ [2-Layer 교안 배포] 각 과목별로 [Layer 1: 직관적 비유] 직후 반드시 [Layer 2: 공학적 한계 교정 가드레일]과 [4단계 기술➔수율➔원가➔영업이익 브릿지]를 함께 제시하여 현업 전이도 극대화",
    ];
  } else if (domain === "UNIVERSAL") {
    const eda = coreOutput.tabular_eda_and_root_cause || {};
    const opt = coreOutput.constrained_optimization_plan || {};
    const rag = coreOutput.document_citation_rag || {};
    const topDriver = eda.root_cause_correlations?.[0];
    const topCit = rag.matched_citations?.[0];
    executiveSummary = `[범용 현업 난제 통합 판정(UNIVERSAL): ${status}] 유효 데이터 ${eda.valid_row_count || 0}건 분석 결과, 핵심 타겟 지표 변동과 가장 상관성이 높은 Root-Cause 변수는 [${topDriver ? `${topDriver.feature} (r=${topDriver.pearson_r})` : "N/A"}]이며, 예산(${opt.utilized_budget}/${opt.total_budget_limit}) 및 용량(${opt.utilized_capacity}/${opt.total_capacity_limit}) 제약 하에서 최적 과업 ${opt.selected_plan?.length || 0}건이 선정되었습니다. (규칙: ${ruleId})`;
    rootCauseHypotheses = [
      `다변량 상관관계 및 스펙 이탈 진단: 스펙 위반 ${eda.spec_violations?.length || 0}건, 센티널/이상치 격리 ${(coreOutput.isolatedAnomalies || []).length}건`,
      topCit
        ? `문서 규정 근거(BM25 Citation): [${topCit.citation_id} - ${topCit.title}] "${topCit.excerpt}"`
        : "문서 규정 검색 결과: 연관 조항 확인 및 기본 안전 가드레일 적용",
    ];
    recommendedSopActions = [
      status === "VIOLATION"
        ? `🚨 [긴급 라인 홀드 및 필수 조치 집행] 스펙 상한(USL) 이탈 또는 필수 과업(${opt.unmet_mandatory_ids?.join(", ") || "Mandatory"}) 예산 부족이 감지되었으므로 근거 규정(${topCit?.citation_id || "SOP"})에 따라 즉시 비상 PM 및 예산 재배정을 실시하십시오.`
        : status === "WARNING"
        ? `⚠️ [보안 구역 제외 및 차순위 과업 이연] 보안 제한 구역(${opt.rejected_restricted_items?.length || 0}건)은 설치/배정에서 원천 배제했으며, 예산 한도로 이연된 ${opt.deferred_items?.length || 0}건은 2차 분기 예산에 반영하십시오.`
        : "✅ [최적 배정안 확정] 모든 제약조건(예산·용량·보안·스펙)을 100% 충족하므로 선정된 최적 계획(Selected Plan)을 현업에 즉시 배포 및 Export 하십시오.",
    ];
  } else {
    executiveSummary = `[무중단 결정론 코어 리포트] 현재 판정 상태는 [${status}] (점수: ${score}점, 적용 규칙: ${ruleId})입니다.`;
    rootCauseHypotheses = [coreOutput?.reason || "결정론적 임계치 규칙에 따른 자동 분류 완료"];
    recommendedSopActions = ["현장 표준 SOP 절차에 따라 1차 수치 근거 확인 후 담당자 승인 진행"];
  }

  return {
    source: errorContext ? "DETERMINISTIC_FALLBACK_ENGINE" : "STRUCTURED_DOMAIN_AI_ADVISOR",
    modelUsed: sanitizeModelName("Sol-6.1"),
    recoveredFrom: errorContext || null,
    domain,
    status,
    ruleId,
    summary: errorContext
      ? `[무중단 안전장치 리포트 (${errorContext} 자동 복구)] ${executiveSummary}`
      : executiveSummary,
    executiveSummary,
    rootCauseHypotheses,
    recommendedSopActions,
    accountabilityNote,
    generatedAt: new Date().toISOString(),
  };
}

/**
 * AI 해석 리포트 생성기 (try-catch 0.1초 무중단 Fallback 내장)
 */
export async function generateInsightWithFallback(coreOutput, options = {}) {
  const safeCore = coreOutput && typeof coreOutput === "object" ? coreOutput : { status: "WARNING", ruleId: "CORE-GUARD" };
  try {
    if (options.simulateError || options.forceTimeout) {
      throw new Error("Simulated_LLM_503_Timeout");
    }
    if (typeof options.customAiCaller === "function") {
      const res = await Promise.race([
        options.customAiCaller(safeCore),
        new Promise((_, reject) => setTimeout(() => reject(new Error("AI_API_TIMEOUT_800MS")), 800)),
      ]);
      if (res && typeof res === "object" && res.summary) {
        return {
          ...buildDeterministicDomainSopReport(safeCore),
          ...res,
          source: "LIVE_LLM_WITH_CORE_GUARD",
          modelUsed: sanitizeModelName(options.model),
        };
      }
    }
    // Browser environment: attempt live backend bridge (/api/ai-expert) with 1200ms timeout
    if (typeof window !== "undefined" && typeof fetch === "function" && options.enableLiveBridge) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 1200);
      const resp = await fetch("/api/ai-expert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ coreOutput: safeCore, model: sanitizeModelName(options.model) }),
        signal: ctrl.signal,
      });
      clearTimeout(timer);
      if (resp.ok) {
        const liveData = await resp.json();
        if (liveData && liveData.summary) {
          return {
            ...buildDeterministicDomainSopReport(safeCore),
            ...liveData,
            modelUsed: sanitizeModelName(liveData.modelUsed || options.model),
          };
        }
      }
    }
    return buildDeterministicDomainSopReport(safeCore, null);
  } catch (err) {
    return buildDeterministicDomainSopReport(safeCore, err?.message || "LLM_SERVICE_UNAVAILABLE");
  }
}

export default generateInsightWithFallback;

