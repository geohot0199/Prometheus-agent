import { describe, expect, it } from 'vitest'

import {
  normalizePrometheusOpenString,
  pathFromPrometheusDeepLink,
  pathFromOpenDeepLink,
  resolvePrometheusOpenPath
} from './prometheus-open-target'

describe('normalizePrometheusOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizePrometheusOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizePrometheusOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped prometheus:// deep links to the same path', () => {
    expect(normalizePrometheusOpenString('prometheus://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizePrometheusOpenString('prometheus://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps prometheus://open/… deep links by stripping the open host', () => {
    expect(normalizePrometheusOpenString('prometheus://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizePrometheusOpenString('prometheus://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved prometheus kinds and unsafe paths', () => {
    expect(normalizePrometheusOpenString('prometheus://blueprint/morning-brief')).toBeNull()
    expect(normalizePrometheusOpenString('prometheus://plugin/install')).toBeNull()
    expect(normalizePrometheusOpenString('https://example.com/x')).toBeNull()
    expect(normalizePrometheusOpenString('/../etc/passwd')).toBeNull()
    expect(normalizePrometheusOpenString('index-network')).toBeNull()
  })
})

describe('resolvePrometheusOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolvePrometheusOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolvePrometheusOpenPath({ href: 'prometheus://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromPrometheusDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromPrometheusDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from prometheus://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromPrometheusDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromPrometheusDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromPrometheusDeepLink('plugin', 'install')).toBeNull()
  })
})
