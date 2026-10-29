/** Colour roles. Categorical hues are assigned to FEATURE categories in fixed order (validated palette). */

export const FEATURE_ORDER = [
  'OS & System Software',
  'Battery & Thermal',
  'Camera & Optics',
  'Connectivity & Network',
  'Display & Touch',
  'Chassis & Build Quality',
  'General Discussion',
] as const

const FEATURE_VAR: Record<string, string> = {
  'OS & System Software': '--s1',
  'Battery & Thermal': '--s2',
  'Camera & Optics': '--s3',
  'Connectivity & Network': '--s4',
  'Display & Touch': '--s5',
  'Chassis & Build Quality': '--s6',
  'General Discussion': '--s7',
}

export const ISSUE_FEATURE: Record<string, string> = {
  'Rapid Battery Drain': 'Battery & Thermal',
  'Thermal Overheating': 'Battery & Thermal',
  'Charging Failure': 'Battery & Thermal',
  'Structural Bending': 'Chassis & Build Quality',
  'Back Cover & Seal Defect': 'Chassis & Build Quality',
  'Screen Artifacts': 'Display & Touch',
  'Touch & Keyboard Lag': 'Display & Touch',
  'Focus & Exposure Bug': 'Camera & Optics',
  'Wireless & Cellular Drop': 'Connectivity & Network',
  'UI Lag & System Freeze': 'OS & System Software',
  'Search & Settings Bug': 'OS & System Software',
  'Non-Defect / General Inquiry': 'General Discussion',
}

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export function featureColor(feature: string): string {
  return cssVar(FEATURE_VAR[feature] ?? '--s7')
}

export function issueColor(issue: string): string {
  return featureColor(ISSUE_FEATURE[issue] ?? 'General Discussion')
}

export function sentimentColor(s: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' | string): string {
  return cssVar(s === 'POSITIVE' ? '--pos' : s === 'NEGATIVE' ? '--neg' : '--neu')
}

export function seq(): string[] {
  return ['--seq-1', '--seq-2', '--seq-3', '--seq-4', '--seq-5'].map(cssVar)
}

export function ink() {
  return {
    ink: cssVar('--ink'),
    ink2: cssVar('--ink-2'),
    ink3: cssVar('--ink-3'),
    line: cssVar('--line'),
    line2: cssVar('--line-2'),
    surface: cssVar('--surface'),
    accent: cssVar('--accent'),
    mono: cssVar('--font-mono'),
    sans: cssVar('--font-sans'),
  }
}

/** Model series: up to 4 compared entities, fixed slot order 1..4. */
export function slotColor(i: number): string {
  return cssVar(['--s1', '--s2', '--s3', '--s6'][i] ?? '--s7')
}
