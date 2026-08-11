export const FAUCET_HIGH_ARC_01 = {
  id: "FAUCET-HIGH-ARC-01",
  heightMm: 340,
  centerlineReachMm: 255,
  baseRadiusMm: 17,
  baseHeightMm: 18,
  bodyRadiusMm: 10,
  bodyHeightMm: 52,
  tubeRadiusMm: 8,
  nozzleRadiusMm: 8,
  nozzleLengthMm: 36,
  aeratorRadiusMm: 9.5,
  aeratorHeightMm: 8,
  leverLengthMm: 48,
  materialDefinitionId: "chrome"
} as const;

export type FaucetPreset = typeof FAUCET_HIGH_ARC_01;
