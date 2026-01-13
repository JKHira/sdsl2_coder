import { SSOT_DEFINITIONS, type SseAuthMode, type SsotToken } from "./ssot_definitions";

const SSOT_REF_RE = new RegExp(SSOT_DEFINITIONS.kernel.token_rules.ssot_ref_pattern);
const CONTRACT_REF_RE = new RegExp(SSOT_DEFINITIONS.kernel.token_rules.contract_ref_pattern);

export function isKnownSsotToken(value: string): value is SsotToken {
  return Object.prototype.hasOwnProperty.call(SSOT_DEFINITIONS.tokens, value);
}

export function listSsotTokens(): SsotToken[] {
  return Object.keys(SSOT_DEFINITIONS.tokens).sort() as SsotToken[];
}

export function getSsotToken(token: SsotToken) {
  return SSOT_DEFINITIONS.tokens[token];
}

export function resolveSsotToken(token: SsotToken): SsotToken {
  let current = token;
  const visited = new Set<SsotToken>();
  while (true) {
    if (visited.has(current)) {
      throw new Error(`SSOT alias cycle detected: ${token}`);
    }
    visited.add(current);
    const def = getSsotToken(current) as { kind?: string; alias_of?: SsotToken };
    if (def.kind === "alias" && def.alias_of) {
      if (!isKnownSsotToken(def.alias_of)) {
        throw new Error(`SSOT alias target missing: ${def.alias_of}`);
      }
      current = def.alias_of;
      continue;
    }
    return current;
  }
}

export function getSsotTokenValue(token: SsotToken): unknown {
  const resolved = resolveSsotToken(token);
  const def = getSsotToken(resolved) as { value?: unknown };
  return def.value;
}

export function isDeferredSsotToken(token: SsotToken): boolean {
  const def = getSsotToken(token) as { kind?: string };
  return def.kind === "ref";
}

export function isValidSsotRef(value: string): boolean {
  return SSOT_REF_RE.test(value);
}

export function isValidContractRef(value: string): boolean {
  return CONTRACT_REF_RE.test(value);
}

export function getSsotTokenSummary(token: SsotToken): string {
  return SSOT_DEFINITIONS.tokens[token].summary;
}

export function isValidSseAuthMode(value: string): value is SseAuthMode {
  return SSOT_DEFINITIONS.enums.SSE_AUTH_MODE.includes(value as SseAuthMode);
}

export function assertValidSseAuthMode(value: string): asserts value is SseAuthMode {
  if (!isValidSseAuthMode(value)) {
    throw new Error(`Invalid SSE auth mode: ${value}`);
  }
}
