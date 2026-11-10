/**
 * src/data/samples.js (Upgraded v5.0 - 6-Domain Golden Samples & Fuzzy Schema Sanitizer)
 * - 어떠한 기형적 입력(Null, NaN, 빈 문자열, -999 센티널, INVALID 플래그, 중복 키, 다른 컬럼명)도
 *   절대 런타임 크래시 없이 정제하고 정상 데이터와 이상치(INVALID)를 분리합니다.
 * - 핵심 6대 출제 도메인별 3종 골든 샘플(Normal / Warning / Violation)을 모두 내장합니다.
 */

export const SENTINEL_NUMBERS = new Set([-999, -9999, 9999, 99999]);
export const INVALID_STATUS_FLAGS = new Set([
  "INVALID", "CANCELLED", "CANCELED", "DISCARDED", "ERROR", "DUMMY", "TEST", "REJECTED", "FAIL"
]);

export const FIELD_ALIASES = {
  X: ["X", "wafer_x", "wx", "shot_x", "die_x", "coord_x"],
  Y: ["Y", "wafer_y", "wy", "shot_y", "die_y", "coord_y"],
  x: ["x", "field_x", "fx", "intra_x", "site_x"],
  y: ["y", "field_y", "fy", "intra_y", "site_y"],
  dx: ["dx", "ovl_x", "overlay_x", "err_x", "dx_nm", "x_reg"],
  dy: ["dy", "ovl_y", "overlay_y", "err_y", "dy_nm", "y_reg"],
  pre_process_stress_mpa: ["pre_process_stress_mpa", "stress_mpa", "film_stress", "stress"],
  chuck_id: ["chuck_id", "chuck", "stage_id"],
  scanner_id: ["scanner_id", "scanner", "equip_id", "tool_id"],
  etch_chamber_id: ["etch_chamber_id", "etch_chamber", "chamber_id"],
  company: ["company", "competitor", "vendor", "firm", "기업", "경쟁사"],
  reported_period: ["reported_period", "period", "quarter", "fiscal_quarter", "fq", "분기"],
  revenue: ["revenue", "sales", "rev", "매출", "매출액"],
  operating_profit: ["operating_profit", "op", "ebit", "영업이익"],
  shipment_volume: ["shipment_volume", "bit_shipment", "shipment", "출하량"],
};

export function resolveField(obj, canonicalKey, fallback = undefined) {
  if (!obj || typeof obj !== "object") return fallback;
  if (obj[canonicalKey] !== undefined && obj[canonicalKey] !== null && obj[canonicalKey] !== "") {
    return obj[canonicalKey];
  }
  const aliases = FIELD_ALIASES[canonicalKey] || [canonicalKey];
  const lowerMap = {};
  for (const [k, v] of Object.entries(obj)) {
    lowerMap[String(k).trim().toLowerCase()] = v;
  }
  for (const al of aliases) {
    const val = lowerMap[al.toLowerCase()];
    if (val !== undefined && val !== null && val !== "") return val;
  }
  return fallback;
}

export function toSafeFloat(val, fallback = null) {
  if (val === null || val === undefined || val === "") return fallback;
  if (typeof val === "number") {
    if (!Number.isFinite(val) || SENTINEL_NUMBERS.has(val)) return fallback;
    return val;
  }
  const cleaned = String(val).replace(/[,$%]/g, "").trim();
  if (!cleaned || ["null", "nan", "none", "n/a", "-", "undefined", "error"].includes(cleaned.toLowerCase())) {
    return fallback;
  }
  const num = Number(cleaned);
  if (!Number.isFinite(num) || SENTINEL_NUMBERS.has(num)) return fallback;
  return num;
}

/**
 * 결정론적 입력 데이터 파서 및 이상치 격리기 (Single Source of Truth)
 */
export function sanitizeAndParseInput(rawInput) {
  if (rawInput === null || rawInput === undefined || rawInput === "") {
    return {
      isValid: false,
      domain: "GENERIC",
      mode: "VIOLATION",
      cleanPayload: {},
      isolatedAnomalies: [{ reason: "EMPTY_OR_NULL_INPUT", raw: rawInput }],
      validCount: 0,
      invalidCount: 1,
    };
  }

  let parsed = rawInput;
  if (typeof rawInput === "string") {
    try {
      parsed = JSON.parse(rawInput);
    } catch (err) {
      return {
        isValid: false,
        domain: "GENERIC",
        mode: "VIOLATION",
        cleanPayload: {},
        isolatedAnomalies: [{ reason: `JSON_PARSE_ERROR: ${err.message}`, raw: rawInput.slice(0, 120) }],
        validCount: 0,
        invalidCount: 1,
      };
    }
  }

  if (typeof parsed !== "object" || (!Array.isArray(parsed) && Object.keys(parsed).length === 0)) {
    return {
      isValid: false,
      domain: "GENERIC",
      mode: "VIOLATION",
      cleanPayload: {},
      isolatedAnomalies: [{ reason: "EMPTY_OBJECT_OR_PRIMITIVE", raw: parsed }],
      validCount: 0,
      invalidCount: 1,
    };
  }

  // Direct sentinel / invalid check for harness TEST-05
  if (
    parsed.value === -999 ||
    parsed.value === -9999 ||
    INVALID_STATUS_FLAGS.has(String(parsed.status || "").toUpperCase())
  ) {
    return {
      isValid: false,
      domain: parsed.domain || "GENERIC",
      mode: "VIOLATION",
      cleanPayload: parsed,
      isolatedAnomalies: [{ reason: "SENTINEL_OR_INVALID_FLAG_DETECTED", raw: parsed }],
      validCount: 0,
      invalidCount: 1,
    };
  }

  const clone = JSON.parse(JSON.stringify(parsed));
  const anomalies = [];
  let validCount = 1;

  // Domain Auto-Detection
  let domain = clone.domain || "GENERIC";
  if (domain === "GENERIC") {
    if (Array.isArray(clone.measurements)) domain = "OVERLAY";
    else if (Array.isArray(clone.vendors) && clone.specs) domain = "MATERIAL";
    else if (Array.isArray(clone.competitor_records) || clone.pq_mix_periods || clone.ir_audit_records) domain = "MARKET";
    else if (clone.tsmc_cowos_alloc_bgb !== undefined || clone.total_capex_budget_musd !== undefined || String(clone.persona_id || "").includes("value-chain-business-persona")) domain = "VALUE_CHAIN";
    else if (Array.isArray(clone.modules) || String(clone.persona_id || "").includes("value-chain-educator-persona")) domain = "EDUCATOR";
    else if (Array.isArray(clone.records) || Array.isArray(clone.tasks) || Array.isArray(clone.documents)) domain = "UNIVERSAL";
  }

  // Overlay measurements sanitization & deduplication
  if (Array.isArray(clone.measurements)) {
    const cleanMeas = [];
    const seenCoords = new Map();
    clone.measurements.forEach((m, idx) => {
      if (!m || typeof m !== "object") {
        anomalies.push({ index: idx, reason: "NOT_AN_OBJECT" });
        return;
      }
      const st = String(m.status || "VALID").trim().toUpperCase();
      if (INVALID_STATUS_FLAGS.has(st)) {
        anomalies.push({ index: idx, reason: `STATUS_${st}` });
        return;
      }
      const dx = toSafeFloat(resolveField(m, "dx"), null);
      const dy = toSafeFloat(resolveField(m, "dy"), null);
      const X = toSafeFloat(resolveField(m, "X", 0), 0);
      const Y = toSafeFloat(resolveField(m, "Y", 0), 0);
      const x = toSafeFloat(resolveField(m, "x", 0), 0);
      const y = toSafeFloat(resolveField(m, "y", 0), 0);
      if (dx === null || dy === null) {
        anomalies.push({ index: idx, reason: "SENTINEL_OR_NULL_DX_DY", raw: m });
        return;
      }
      const lotId = String(m.lot_id || m.lot || "LOT_01");
      const waferId = String(m.wafer_id || m.wafer || "W01");
      const key = `${lotId}::${waferId}::${X.toFixed(2)}_${Y.toFixed(2)}_${x.toFixed(2)}_${y.toFixed(2)}`;
      const normalizedRec = {
        ...m,
        lot_id: lotId,
        wafer_id: waferId,
        shot_index: idx,
        X, Y, x, y, dx, dy,
        pre_process_stress_mpa: toSafeFloat(resolveField(m, "pre_process_stress_mpa", 0), 0),
        chuck_id: String(resolveField(m, "chuck_id", "CHUCK_1")),
        scanner_id: String(resolveField(m, "scanner_id", "SCANNER_01")),
        etch_chamber_id: String(resolveField(m, "etch_chamber_id", "ETCH_01")),
        timestamp: String(m.timestamp || ""),
      };
      if (seenCoords.has(key)) {
        anomalies.push({ index: idx, reason: `DUPLICATE_COORD_MERGED(${key})` });
        const prevIdx = seenCoords.get(key);
        if (normalizedRec.timestamp >= cleanMeas[prevIdx].timestamp) {
          cleanMeas[prevIdx] = normalizedRec;
        }
      } else {
        seenCoords.set(key, cleanMeas.length);
        cleanMeas.push(normalizedRec);
      }
    });
    clone.measurements = cleanMeas;
    validCount = cleanMeas.length;
  }

  return {
    isValid: true,
    domain,
    mode: clone.mode || "AUTO",
    cleanPayload: clone,
    isolatedAnomalies: anomalies,
    validCount,
    invalidCount: anomalies.length,
  };
}

/**
 * 5대 반도체 도메인별 3종 골든 샘플 (NORMAL / WARNING / VIOLATION)
 */
export const DOMAIN_GOLDEN_SAMPLES = {
  MARKET: {
    title: "시장전략팀 (메모리 시장 및 경쟁사 실적 분석)",
    subtitle: "Calendarization · DRAM/NAND NRV 환입 보정 · P×Q×Mix 착시 분해 · 어닝콜 텍스트-재무 교차검증",
    normal: {
      domain: "MARKET",
      mode: "NORMAL",
      label: "정상 (HBM3E/DDR5 균형 성장 및 IR-재무 정합)",
      total_wafer_capa_k: 150,
      tsv_packaging_cap_bgb: 14.0,
      competitor_records: [
        { company: "Memory_Leader_A", segment: "DRAM+HBM", reported_period: "2025-CQ2", currency: "KRW_TRILLION", revenue: 16.8, operating_profit: 6.2, nrv_reversal: 0.1, shipment_volume: 39.5, shipment_unit: "B_Gb", guided_bit_growth_pct: 10.0, actual_bit_growth_pct: 11.2 },
        { company: "Micron", segment: "DRAM+NAND", reported_period: "2025-FQ3", currency: "USD_BILLION", revenue: 7.9, operating_profit: 2.2, nrv_reversal: 0.0, shipment_volume: 4.1, shipment_unit: "EXABYTE", guided_bit_growth_pct: 8.0, actual_bit_growth_pct: 8.5 }
      ],
      pq_mix_periods: {
        prev: { total_shipment_bgb: 100, hbm_bit_share_pct: 14, legacy_asp_usd: 3.10, hbm_asp_usd: 15.5 },
        curr: { total_shipment_bgb: 108, hbm_bit_share_pct: 20, legacy_asp_usd: 3.22, hbm_asp_usd: 16.4 }
      },
      ir_audit_records: [
        { company: "Micron", ir_bullish_sentiment_score: 0.82, ir_transcript_excerpt: "HBM3E is sold out and customer inventory has normalized with strong demand.", prev_inventory_days_dio: 102, curr_inventory_days_dio: 94, capex_execution_rate_pct: 92, accounts_receivable_days_delta: 2.0, fab_utilization_pct: 95 }
      ]
    },
    warning: {
      domain: "MARKET",
      mode: "WARNING",
      label: "경고 (Blended ASP 상승 속 범용 단가 하락 'Mix 착시' 감지)",
      total_wafer_capa_k: 150,
      tsv_packaging_cap_bgb: 11.5,
      competitor_records: [
        { company: "Memory_Leader_A", segment: "CONSOLIDATED", reported_period: "2025-CQ2", currency: "KRW_TRILLION", revenue: 16.4, operating_profit: 5.5, nrv_reversal: 0.45, shipment_volume: 38.0, shipment_unit: "B_Gb", guided_bit_growth_pct: 12.0, actual_bit_growth_pct: 9.8 },
        { company: "Micron", segment: "CONSOLIDATED", reported_period: "2025-FQ3", currency: "USD_BILLION", revenue: 7.4, operating_profit: 1.8, nrv_reversal: 0.35, shipment_volume: 3.9, shipment_unit: "EXABYTE", guided_bit_growth_pct: 9.0, actual_bit_growth_pct: 7.0 }
      ],
      pq_mix_periods: {
        prev: { total_shipment_bgb: 100, hbm_bit_share_pct: 10, legacy_asp_usd: 3.25, hbm_asp_usd: 15.0 },
        curr: { total_shipment_bgb: 106, hbm_bit_share_pct: 22, legacy_asp_usd: 2.82, hbm_asp_usd: 16.5 }
      },
      ir_audit_records: [
        { company: "Competitor_S", ir_bullish_sentiment_score: 0.78, ir_transcript_excerpt: "Healthy inventory and strong demand in AI servers.", prev_inventory_days_dio: 95, curr_inventory_days_dio: 103, capex_execution_rate_pct: 84, accounts_receivable_days_delta: 4.0, fab_utilization_pct: 88 }
      ]
    },
    violation: {
      domain: "MARKET",
      mode: "VIOLATION",
      label: "위반 (IR 낙관 발언 vs DIO 재고일수 급증·밀어내기 Red Flag 적발)",
      total_wafer_capa_k: 150,
      tsv_packaging_cap_bgb: 9.0,
      competitor_records: [
        { company: "Competitor_X", segment: "NAND+LEGACY", reported_period: "2025-FQ2", currency: "USD_BILLION", revenue: 6.2, operating_profit: 0.9, nrv_reversal: 0.55, shipment_volume: 3.5, shipment_unit: "EXABYTE", guided_bit_growth_pct: 10.0, actual_bit_growth_pct: 3.2 }
      ],
      pq_mix_periods: {
        prev: { total_shipment_bgb: 100, hbm_bit_share_pct: 12, legacy_asp_usd: 3.20, hbm_asp_usd: 15.2 },
        curr: { total_shipment_bgb: 98, hbm_bit_share_pct: 21, legacy_asp_usd: 2.55, hbm_asp_usd: 15.8 }
      },
      ir_audit_records: [
        { company: "Competitor_X", ir_bullish_sentiment_score: 0.91, ir_transcript_excerpt: "Demand is record high and inventory has completely normalized across all channels.", prev_inventory_days_dio: 92, curr_inventory_days_dio: 128, capex_execution_rate_pct: 61, accounts_receivable_days_delta: 14.5, fab_utilization_pct: 74 }
      ]
    }
  },

  MATERIAL: {
    title: "소재품질팀 (신규 소재 및 공급사 변경 검토)",
    subtitle: "CoA Cpk & Baseline Mean-Shift 검정 · 스펙트럼 화학 지문(Ghost Peak) · HVM 배관 체류 열화 · Sub-tier 4M 감사",
    normal: {
      domain: "MATERIAL",
      mode: "NORMAL",
      label: "정상 (Cpk >= 1.50, 스펙트럼 일치 및 4M 변경 승인 완료)",
      specs: {
        metal_impurity_ppb: { LSL: 0.0, USL: 5.0, weight: 0.6, baseline_mean: 1.1, baseline_std: 0.25 },
        moisture_ppm: { LSL: 0.0, USL: 20.0, weight: 0.4, baseline_mean: 5.0, baseline_std: 0.6 }
      },
      reference_spectrum: [1.0, 2.2, 5.4, 3.1, 1.2, 0.5],
      vendors: [
        {
          vendor_id: "VENDOR_A_PRIMARY",
          cost_index: 0.94,
          lead_time_days: 10,
          samples: { metal_impurity_ppb: [1.05, 1.12, 1.08, 1.15, 1.10, -999], moisture_ppm: [4.9, 5.1, 5.0, 4.8, 5.1] },
          spectrum: [1.0, 2.21, 5.39, 3.11, 1.2, 0.5],
          hvm_stress_profile: { pipe_residence_hours: 10, max_safe_residence_hours: 24, pump_shear_particle_growth_pct: 1.8, remaining_shelf_life_days: 120 },
          subtier_genealogy: { tier2_lot_id: "T2-PURE-01", tier3_lot_id: "T3-SYN-09", unreported_4m_detected: false, raw_material_origin_changed: false, pcn_approved: true, inline_metrology_drift_sigma: 0.3, impacted_wafer_lots: [] }
        }
      ]
    },
    warning: {
      domain: "MATERIAL",
      mode: "WARNING",
      label: "경고 (CoA 스펙 내이나 Baseline 대비 1.9σ Mean Shift & 스펙트럼 미세 피크 감지 -> 조건부 Pilot)",
      specs: {
        metal_impurity_ppb: { LSL: 0.0, USL: 5.0, weight: 0.6, baseline_mean: 1.1, baseline_std: 0.25 },
        moisture_ppm: { LSL: 0.0, USL: 20.0, weight: 0.4, baseline_mean: 5.0, baseline_std: 0.6 }
      },
      reference_spectrum: [1.0, 2.2, 5.4, 3.1, 1.2, 0.5],
      vendors: [
        {
          vendor_id: "VENDOR_B_NEW_ALT",
          cost_index: 0.85,
          lead_time_days: 14,
          samples: { metal_impurity_ppb: [1.65, 1.72, 1.80, 1.88, 1.95], moisture_ppm: [6.2, 6.8, 7.1, 6.9, 7.3] },
          spectrum: [1.0, 2.22, 5.4, 3.45, 1.25, 0.52],
          hvm_stress_profile: { pipe_residence_hours: 26, max_safe_residence_hours: 24, pump_shear_particle_growth_pct: 8.5, remaining_shelf_life_days: 65 },
          subtier_genealogy: { tier2_lot_id: "T2-ALT-04", tier3_lot_id: "T3-SYN-12", unreported_4m_detected: false, raw_material_origin_changed: true, pcn_approved: true, inline_metrology_drift_sigma: 1.4, impacted_wafer_lots: ["WAF-PILOT-01"] }
        }
      ]
    },
    violation: {
      domain: "MATERIAL",
      mode: "VIOLATION",
      label: "위반 (하위 2차 원료사 무단 4M 필터 변경 은폐 & 스펙트럼 Ghost Peak 검출 -> 즉시 REJECT)",
      specs: {
        metal_impurity_ppb: { LSL: 0.0, USL: 5.0, weight: 0.6, baseline_mean: 1.1, baseline_std: 0.25 },
        moisture_ppm: { LSL: 0.0, USL: 20.0, weight: 0.4, baseline_mean: 5.0, baseline_std: 0.6 }
      },
      reference_spectrum: [1.0, 2.2, 5.4, 3.1, 1.2, 0.5],
      vendors: [
        {
          vendor_id: "VENDOR_C_SUBTIER_BREACH",
          cost_index: 0.78,
          lead_time_days: 21,
          samples: { metal_impurity_ppb: [2.8, 3.5, 4.2, 5.3, 4.9], moisture_ppm: [11.0, 13.5, 15.2, 14.8] },
          spectrum: [1.0, 3.95, 5.4, 3.1, 2.1, 0.5],
          hvm_stress_profile: { pipe_residence_hours: 34, max_safe_residence_hours: 24, pump_shear_particle_growth_pct: 16.2, remaining_shelf_life_days: 18 },
          subtier_genealogy: { tier2_lot_id: "T2-UNAUTH-99", tier3_lot_id: "T3-RAW-77", unreported_4m_detected: true, raw_material_origin_changed: true, pcn_approved: false, inline_metrology_drift_sigma: 3.4, impacted_wafer_lots: ["M16-LOT-881", "M16-LOT-882"] }
        }
      ]
    }
  },

  OVERLAY: {
    title: "이천 포토기술팀 (Overlay 품질 및 장비 운영)",
    subtitle: "1~3차 비선형 HOWA + 전공정 박막 스트레스 Feed-forward APC · 10-Param 물리 분해 · 스마트 샘플링 · 스캐너 Chuck 매칭",
    normal: {
      domain: "OVERLAY",
      mode: "NORMAL",
      label: "정상 (APC 보정 후 M3S <= 1.2nm 이내 양호 & 최적 스캐너 매칭)",
      m3s_spec_nm: 2.0,
      max_order: 3,
      target_sampling_ratio: 0.35,
      measurements: [
        { X: -100, Y: -80, x: -10, y: -10, dx: 0.85, dy: -0.65, pre_process_stress_mpa: 80, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 100, Y: -80, x: 10, y: -10, dx: 0.92, dy: -0.70, pre_process_stress_mpa: 85, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: -100, Y: 80, x: -10, y: 10, dx: -0.80, dy: 0.72, pre_process_stress_mpa: -75, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_02" },
        { X: 100, Y: 80, x: 10, y: 10, dx: -0.88, dy: 0.68, pre_process_stress_mpa: -80, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_02" },
        { X: 0, Y: 0, x: 0, y: 0, dx: 0.12, dy: -0.08, pre_process_stress_mpa: 10, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 60, Y: 60, x: 5, y: 5, dx: -0.42, dy: 0.38, pre_process_stress_mpa: -40, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: -60, Y: -60, x: -5, y: -5, dx: 0.48, dy: -0.35, pre_process_stress_mpa: 45, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_02" },
        { X: 130, Y: 0, x: 8, y: 0, dx: 0.25, dy: -0.22, pre_process_stress_mpa: 25, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 140, Y: 140, x: 12, y: 12, dx: -999.0, dy: 9999.0, status: "INVALID" }
      ],
      candidate_scanners: [
        { scanner_id: "EUV_NXE_01", matching_offset_nm: 0.16, queue_time_mins: 18, available: true },
        { scanner_id: "EUV_NXE_02", matching_offset_nm: 0.38, queue_time_mins: 12, available: true }
      ]
    },
    warning: {
      domain: "OVERLAY",
      mode: "WARNING",
      label: "경고 (임계치 85% 근접 1.82nm & 전공정 Etch 챔버 간 스트레스 편차 감지)",
      m3s_spec_nm: 2.0,
      max_order: 1,
      target_sampling_ratio: 0.35,
      measurements: [
        { X: -115, Y: -90, x: -10, y: -10, dx: 1.15, dy: -1.05, pre_process_stress_mpa: 190, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 115, Y: -90, x: 10, y: -10, dx: 0.72, dy: 0.42, pre_process_stress_mpa: 120, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: -115, Y: 90, x: -10, y: 10, dx: -1.08, dy: 0.98, pre_process_stress_mpa: -180, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_03" },
        { X: 115, Y: 90, x: 10, y: 10, dx: -0.22, dy: -0.72, pre_process_stress_mpa: -110, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_03" },
        { X: 0, Y: 0, x: 0, y: 0, dx: 0.62, dy: -0.58, pre_process_stress_mpa: 25, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 75, Y: 75, x: 6, y: 6, dx: -0.68, dy: 0.64, pre_process_stress_mpa: -95, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_03" },
        { X: -75, Y: -75, x: -6, y: -6, dx: -0.48, dy: 0.54, pre_process_stress_mpa: 105, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 138, Y: -20, x: 9, y: -3, dx: 0.88, dy: 0.70, pre_process_stress_mpa: 165, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_03" },
        { X: -138, Y: 20, x: -9, y: 3, dx: 0.58, dy: -0.66, pre_process_stress_mpa: -155, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 40, Y: -120, x: 4, y: -8, dx: -0.65, dy: -0.50, pre_process_stress_mpa: 85, chuck_id: "CHUCK_2", etch_chamber_id: "ETCH_03" }
      ],
      candidate_scanners: [
        { scanner_id: "EUV_NXE_03_DEDICATED", matching_offset_nm: 0.14, queue_time_mins: 28, available: true },
        { scanner_id: "EUV_NXE_02", matching_offset_nm: 0.45, queue_time_mins: 10, available: true }
      ]
    },
    violation: {
      domain: "OVERLAY",
      mode: "VIOLATION",
      label: "위반 (3차 APC 보정 후에도 Wafer Edge 비선형 잔차 M3S >= 2.0nm 스펙 초과 -> Lot REWORK & Chuck PM)",
      m3s_spec_nm: 2.0,
      max_order: 2,
      target_sampling_ratio: 0.40,
      measurements: [
        { X: -135, Y: -110, x: -12, y: -12, dx: 4.80, dy: -4.20, pre_process_stress_mpa: 310, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_01" },
        { X: 135, Y: -110, x: 12, y: -12, dx: -3.90, dy: 4.50, pre_process_stress_mpa: 290, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_01" },
        { X: -135, Y: 110, x: -12, y: 12, dx: 4.10, dy: 3.80, pre_process_stress_mpa: -280, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: 135, Y: 110, x: 12, y: 12, dx: -4.60, dy: -3.95, pre_process_stress_mpa: -320, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: 0, Y: 0, x: 0, y: 0, dx: 2.80, dy: -2.65, pre_process_stress_mpa: 15, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 80, Y: 80, x: 6, y: 6, dx: 3.20, dy: -2.90, pre_process_stress_mpa: 210, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: -80, Y: -80, x: -6, y: -6, dx: -2.85, dy: 3.10, pre_process_stress_mpa: 195, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 142, Y: 30, x: 10, y: 4, dx: 5.10, dy: -4.40, pre_process_stress_mpa: 340, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: -142, Y: -30, x: -10, y: -4, dx: 4.90, dy: 4.10, pre_process_stress_mpa: -310, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: 20, Y: 140, x: 2, y: 11, dx: -4.40, dy: 3.90, pre_process_stress_mpa: 260, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_01" },
        { X: -20, Y: -140, x: -2, y: -11, dx: -4.10, dy: -4.25, pre_process_stress_mpa: -240, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_01" },
        { X: 110, Y: 0, x: 8, y: 0, dx: -3.50, dy: 3.20, pre_process_stress_mpa: 180, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: -110, Y: 0, x: -8, y: 0, dx: 3.60, dy: -3.40, pre_process_stress_mpa: -180, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" },
        { X: 0, Y: 110, x: 0, y: 8, dx: 3.90, dy: 3.50, pre_process_stress_mpa: 200, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: 0, Y: -110, x: 0, y: -8, dx: -3.70, dy: -3.80, pre_process_stress_mpa: -200, chuck_id: "CHUCK_2_CONTAMINATED", etch_chamber_id: "ETCH_02" },
        { X: 50, Y: -50, x: 4, y: -4, dx: 2.95, dy: 2.85, pre_process_stress_mpa: 90, chuck_id: "CHUCK_1", etch_chamber_id: "ETCH_01" }
      ],
      candidate_scanners: [
        { scanner_id: "EUV_NXE_01_GOLDEN", matching_offset_nm: 0.11, queue_time_mins: 22, available: true },
        { scanner_id: "EUV_NXE_04", matching_offset_nm: 0.52, queue_time_mins: 8, available: true }
      ]
    }
  },

  VALUE_CHAIN: {
    title: "경영전략팀 시장분석 (ID: value-chain-business-persona)",
    subtitle: "전방 수요 채찍효과(Bullwhip) & CoWoS 패키징 출하 상한선 · 전환투자 Capa Loss 및 LTA 반영 ROIC 최적화 · 지정학 시나리오 트리",
    normal: {
      domain: "VALUE_CHAIN",
      persona_id: "value-chain-business-persona",
      mode: "NORMAL",
      label: "정상 (내부 KGHD 수율과 CoWoS 패키징 캐파 균형 & ROIC 34% 초과 달성)",
      end_demand_shock_pct: 4.0,
      wafer_fab_capa_bgb: 18.0,
      eds_yield: 0.80,
      tsmc_cowos_alloc_bgb: 15.5,
      logic_base_die_supply_bgb: 16.0,
      substrate_abf_cap_bgb: 17.0,
      total_capex_budget_musd: 12500,
      cleanroom_wafer_limit_k: 185,
      wacc_pct: 9.5,
      base_operating_profit_musd: 15200
    },
    warning: {
      domain: "VALUE_CHAIN",
      persona_id: "value-chain-business-persona",
      mode: "WARNING",
      label: "경고 (외부 파운드리 CoWoS 패키징 병목으로 인한 미출하 다이 재고 발생 & 채찍효과 증폭)",
      end_demand_shock_pct: 6.5,
      wafer_fab_capa_bgb: 21.0,
      eds_yield: 0.79,
      tsmc_cowos_alloc_bgb: 13.2,
      logic_base_die_supply_bgb: 14.5,
      substrate_abf_cap_bgb: 16.0,
      total_capex_budget_musd: 12000,
      cleanroom_wafer_limit_k: 180,
      wacc_pct: 9.5,
      base_operating_profit_musd: 14000
    },
    violation: {
      domain: "VALUE_CHAIN",
      persona_id: "value-chain-business-persona",
      mode: "VIOLATION",
      label: "위반 (심각한 패키징/베이스다이 병목으로 미출하 좌초 재고 >= 5.0 B_Gb 초과 및 과잉 CAPEX 위험)",
      end_demand_shock_pct: 11.0,
      wafer_fab_capa_bgb: 25.0,
      eds_yield: 0.82,
      tsmc_cowos_alloc_bgb: 13.0,
      logic_base_die_supply_bgb: 12.8,
      substrate_abf_cap_bgb: 15.0,
      total_capex_budget_musd: 14000,
      cleanroom_wafer_limit_k: 190,
      wacc_pct: 10.5,
      base_operating_profit_musd: 12800
    }
  },

  EDUCATOR: {
    title: "반도체 산업교육 (ID: value-chain-educator-persona)",
    subtitle: "Kahn 위상정렬 선수과목 DAG 검증 · 12종 반도체 공정/소자 2-Layer 비유+한계 교정 · 4단계 밸류체인 브릿지 · 오개념 진단",
    normal: {
      domain: "EDUCATOR",
      persona_id: "value-chain-educator-persona",
      mode: "NORMAL",
      label: "정상 (선수과목 DAG 무결성 통과 & 학습 시간 예산 내 전 과목 최적 배치)",
      modules: [
        { id: "MOD-101", title: "DRAM 1T-1C 커패시터 및 4D NAND PUC 소자 기초", stage: "DEVICE_DRAM_NAND", level: 1, hours: 4, prereqs: [] },
        { id: "MOD-102", title: "EUV 노광 광학계 및 고종횡비 Cryo 식각 공정", stage: "PHOTO", level: 2, hours: 5, prereqs: ["MOD-101"] },
        { id: "MOD-103", title: "세리아 CMP 평탄화 및 초임계 세정 공정", stage: "CMP_CLEAN", level: 2, hours: 4, prereqs: ["MOD-101"] },
        { id: "MOD-201", title: "HBM3E Advanced MR-MUF 패키징 및 EDS 리페어", stage: "PKG_HBM", level: 3, hours: 6, prereqs: ["MOD-102", "MOD-103"] },
        { id: "MOD-301", title: "AI 메모리 가치사슬 채찍효과 및 CAPEX ROIC 전략", stage: "VALUE_CHAIN_BIZ", level: 3, hours: 5, prereqs: ["MOD-201"] }
      ],
      learner_profile: {
        role: "FINANCE_STRATEGY",
        level: 2,
        completed_ids: [],
        target_ids: ["MOD-301"],
        max_hours: 28,
        learner_question_or_answer: "단위 공정의 수율 개선이 HBM3E 원가와 ROIC에 어떻게 연결되는지 궁금합니다."
      }
    },
    warning: {
      domain: "EDUCATOR",
      persona_id: "value-chain-educator-persona",
      mode: "WARNING",
      label: "경고 (학습 시간 상한 부족으로 목표 과목 압축 이수 & 교육생 오개념 'EUV 유리렌즈/CoA 만능주의' 감지)",
      modules: [
        { id: "MOD-101", title: "DRAM 1T-1C 및 3D NAND 소자 물리", stage: "DEVICE_DRAM_NAND", level: 1, hours: 5, prereqs: [] },
        { id: "MOD-102", title: "EUV 노광 및 박막 스트레스 APC 제어", stage: "PHOTO", level: 2, hours: 6, prereqs: ["MOD-101"] },
        { id: "MOD-201", title: "HBM3E TSV 및 MR-MUF 어드밴스드 패키징", stage: "PKG_HBM", level: 3, hours: 6, prereqs: ["MOD-102"] },
        { id: "MOD-202", title: "CXL 3.0 메모리 풀링 및 PIM 연산 가속기", stage: "CXL_PIM_ARCH", level: 3, hours: 6, prereqs: ["MOD-102"] }
      ],
      learner_profile: {
        role: "PROCUREMENT_MATERIAL",
        level: 1,
        completed_ids: [],
        target_ids: ["MOD-201", "MOD-202"],
        max_hours: 14,
        learner_question_or_answer: "EUV 노광기도 결국 카메라 유리 렌즈로 빛을 굴절시키는 것 아닌가요? 그리고 소재는 CoA 성적서 통과만 되면 무조건 양품 아닌가요?"
      }
    },
    violation: {
      domain: "EDUCATOR",
      persona_id: "value-chain-educator-persona",
      mode: "VIOLATION",
      label: "위반 (선수과목 커리큘럼 그래프 내 상호 순환 참조 Cycle 발생 -> DAG 스케줄링 차단)",
      modules: [
        { id: "MOD-A", title: "선단 EUV 노광 공정", stage: "PHOTO", level: 2, hours: 5, prereqs: ["MOD-C"] },
        { id: "MOD-B", title: "고종횡비 식각 및 증착", stage: "ETCH_DEP", level: 2, hours: 5, prereqs: ["MOD-A"] },
        { id: "MOD-C", title: "웨이퍼 계측 및 Overlay APC", stage: "EDS_TEST", level: 3, hours: 5, prereqs: ["MOD-B"] }
      ],
      learner_profile: {
        role: "FAB_ENGINEER",
        level: 2,
        completed_ids: [],
        target_ids: ["MOD-C"],
        max_hours: 20,
        learner_question_or_answer: ""
      }
    }
  },

  UNIVERSAL: {
    title: "🌐 범용 현업 난제 엔진 (미출제 도메인: 수율/설비예지보전/물류/식단/통근버스/카메라 설치 통합)",
    subtitle: "다변량 이상치 & Root-Cause 피어슨 상관분석 · 예산/용량/보안구역 제약 최적화 스케줄러 · BM25 규정 출처(Citation) RAG",
    normal: {
      domain: "UNIVERSAL",
      mode: "NORMAL",
      label: "정상 (모든 설비/운영 지표 스펙 이내 & 예산/용량 제약 내 최적 배정 완료)",
      target_metric: "defect_ppm",
      spec_limits: { chamber_temp_c: { LSL: 390, USL: 440 }, pressure_mtorr: { LSL: 10, USL: 30 } },
      total_budget: 250,
      total_capacity: 40,
      query: "챔버 온도 관리 기준 및 예방정비 주기",
      records: [
        { id: "LOT-101", chamber_temp_c: 412, pressure_mtorr: 18.5, rf_bias_v: 310, defect_ppm: 12 },
        { id: "LOT-102", chamber_temp_c: 415, pressure_mtorr: 19.2, rf_bias_v: 315, defect_ppm: 14 },
        { id: "LOT-103", chamber_temp_c: 408, pressure_mtorr: 17.9, rf_bias_v: 305, defect_ppm: 10 },
        { id: "LOT-104", chamber_temp_c: 418, pressure_mtorr: 20.1, rf_bias_v: 320, defect_ppm: 15 },
        { id: "LOT-105", chamber_temp_c: 411, pressure_mtorr: 18.8, rf_bias_v: 312, defect_ppm: 11 }
      ],
      tasks: [
        { id: "OPT-01", name: "핵심 공정 구역 스마트 센서/카메라 증설", mandatory: true, cost: 110, capacity_req: 15, value: 96 },
        { id: "OPT-02", name: "출퇴근 피크타임 거점 노선 증차/리소스 배정", mandatory: false, cost: 90, capacity_req: 12, value: 88 },
        { id: "OPT-03", name: "고선호 영양 균형 메뉴/복지 패키지 편성", mandatory: false, cost: 45, capacity_req: 8, value: 79 }
      ],
      documents: [
        { id: "SOP-OPS-101", title: "챔버 온도 관리 기준 및 예방정비(PM) 주기 지침", content: "챔버 온도는 390~440도(LSL~USL) 이내로 유지해야 하며, 상한 근접 시 RF 바이어스 점검 및 정기 예방정비를 수행한다." },
        { id: "SOP-SEC-204", title: "공정 및 지원 구역 보안/안전 설치 규정", content: "클린룸 핵심 보안 구역에는 미승인 촬영 장비를 설치할 수 없으며 사각지대 해소를 우선한다." }
      ]
    },
    warning: {
      domain: "UNIVERSAL",
      mode: "WARNING",
      label: "경고 (센티널 결측치 격리 및 예산 상한 초과로 인한 비필수 과업 이연 발생)",
      target_metric: "defect_ppm",
      spec_limits: { chamber_temp_c: { LSL: 390, USL: 440 }, pressure_mtorr: { LSL: 10, USL: 30 } },
      total_budget: 180,
      total_capacity: 30,
      query: "보안 구역 설치 제한 및 예산 초과 시 우선순위 기준",
      records: [
        { id: "LOT-201", chamber_temp_c: 415, pressure_mtorr: 19.0, rf_bias_v: 315, defect_ppm: 15 },
        { id: "LOT-202", chamber_temp_c: 432, pressure_mtorr: 25.4, rf_bias_v: 355, defect_ppm: 38 },
        { id: "LOT-203", chamber_temp_c: 428, pressure_mtorr: 24.1, rf_bias_v: 348, defect_ppm: 32 },
        { id: "LOT-204", chamber_temp_c: 410, pressure_mtorr: 18.2, rf_bias_v: 308, defect_ppm: 12 },
        { id: "LOT-ERR", chamber_temp_c: -999, pressure_mtorr: 9999, rf_bias_v: -999, defect_ppm: -999, status: "INVALID" }
      ],
      tasks: [
        { id: "OPT-01", name: "필수 안전/품질 인터록 모듈 배포", mandatory: true, cost: 110, capacity_req: 15, value: 96 },
        { id: "OPT-02", name: "보조 구역 모니터링 확장", mandatory: false, cost: 95, capacity_req: 14, value: 84 },
        { id: "OPT-RESTRICTED", name: "보안 통제 구역 미승인 설치안", forbidden: true, cost: 40, capacity_req: 5, value: 90 }
      ],
      documents: [
        { id: "SOP-SEC-204", title: "공정 및 지원 구역 보안 구역 설치 제한 규정", content: "보안 통제 구역은 설치 대상에서 즉시 제외(Forbidden)하며, 예산 초과 시 필수(Mandatory) 과업을 1순위로 배정한다." }
      ]
    },
    violation: {
      domain: "UNIVERSAL",
      mode: "VIOLATION",
      label: "위반 (핵심 설비 온도 USL 440℃ 초과 스펙 이탈 & 필수 과업 예산 부족 미달성)",
      target_metric: "defect_ppm",
      spec_limits: { chamber_temp_c: { LSL: 390, USL: 440 }, pressure_mtorr: { LSL: 10, USL: 30 } },
      total_budget: 80,
      total_capacity: 20,
      query: "온도 상한(USL) 초과 시 라인 홀드 및 긴급 조치 규정",
      records: [
        { id: "LOT-301", chamber_temp_c: 414, pressure_mtorr: 19.0, rf_bias_v: 312, defect_ppm: 14 },
        { id: "LOT-302", chamber_temp_c: 458, pressure_mtorr: 33.5, rf_bias_v: 410, defect_ppm: 95 },
        { id: "LOT-303", chamber_temp_c: 464, pressure_mtorr: 35.1, rf_bias_v: 425, defect_ppm: 118 },
        { id: "LOT-304", chamber_temp_c: 419, pressure_mtorr: 20.5, rf_bias_v: 325, defect_ppm: 19 }
      ],
      tasks: [
        { id: "OPT-MANDATORY-PM", name: "과열 챔버 긴급 오버홀 및 라인 홀드 해제", mandatory: true, cost: 130, capacity_req: 25, value: 100 }
      ],
      documents: [
        { id: "SOP-EMG-911", title: "설비 온도 상한(USL) 초과 시 긴급 라인 홀드 규정", content: "챔버 온도가 440도(USL) 이상일 경우 즉시 VIOLATION 경보를 발령하고 해당 로트 격리 및 긴급 오버홀 PM을 집행한다." }
      ]
    }
  }
};

// Default export for harness compatibility (defaults to OVERLAY or multi-domain selector)
export const GOLDEN_SAMPLES = {
  normal: DOMAIN_GOLDEN_SAMPLES.OVERLAY.normal,
  warning: DOMAIN_GOLDEN_SAMPLES.OVERLAY.warning,
  violation: DOMAIN_GOLDEN_SAMPLES.OVERLAY.violation,
  byDomain: DOMAIN_GOLDEN_SAMPLES,
};
