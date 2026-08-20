import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.prometheusDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('prometheus:translucency:support')

contextBridge.exposeInMainWorld('prometheusDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  getConnection: profile => ipcRenderer.invoke('prometheus:connection', profile),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('prometheus:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('prometheus:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('prometheus:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('prometheus:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('prometheus:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('prometheus:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('prometheus:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('prometheus:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('prometheus:window:openInTerminal', sessionId, opts),
  openWindow: () => ipcRenderer.invoke('prometheus:window:openInstance'),
  claimAmbientCue: key => ipcRenderer.invoke('prometheus:ambient:claim', key),
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('prometheus:wake-indicator:get'),
    setState: state => ipcRenderer.send('prometheus:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('prometheus:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('prometheus:wake-indicator:state', listener)
    }
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('prometheus:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('prometheus:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('prometheus:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('prometheus:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('prometheus:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('prometheus:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('prometheus:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('prometheus:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('prometheus:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    open: request => ipcRenderer.invoke('prometheus:hud:open', request),
    close: () => ipcRenderer.invoke('prometheus:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('prometheus:hud:ignore-mouse', ignore),
    moveBy: delta => ipcRenderer.send('prometheus:hud:move-by', delta),
    setBounds: bounds => ipcRenderer.send('prometheus:hud:set-bounds', bounds),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('prometheus:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('prometheus:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('prometheus:hud:goto', listener)

      return () => ipcRenderer.removeListener('prometheus:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('prometheus:hud:changed', listener)

      return () => ipcRenderer.removeListener('prometheus:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('prometheus:hud:cursor', listener)

      return () => ipcRenderer.removeListener('prometheus:hud:cursor', listener)
    }
  },
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('prometheus:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('prometheus:quick-entry:settings:set', patch),
    submit: payload => ipcRenderer.send('prometheus:quick-entry:submit', payload),
    dismiss: () => ipcRenderer.send('prometheus:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('prometheus:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('prometheus:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('prometheus:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('prometheus:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('prometheus:quick-entry:shown', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('prometheus:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('prometheus:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('prometheus:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('prometheus:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('prometheus:connection-config:test', payload),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('prometheus:connections:list'),
    save: payload => ipcRenderer.invoke('prometheus:connections:save', payload),
    remove: id => ipcRenderer.invoke('prometheus:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('prometheus:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('prometheus:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('prometheus:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('prometheus:connections:test', id),
    // Fan out `prometheus update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('prometheus:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:connections:changed', listener)

      return () => ipcRenderer.removeListener('prometheus:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('prometheus:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('prometheus:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('prometheus:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('prometheus:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('prometheus:connection-config:oauth-logout', remoteUrl),
  // Prometheus Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('prometheus:cloud:status'),
    login: () => ipcRenderer.invoke('prometheus:cloud:login'),
    logout: () => ipcRenderer.invoke('prometheus:cloud:logout'),
    discover: org => ipcRenderer.invoke('prometheus:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('prometheus:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('prometheus:profile:get'),
    set: name => ipcRenderer.invoke('prometheus:profile:set', name)
  },
  api: request => ipcRenderer.invoke('prometheus:api', request),
  notify: payload => ipcRenderer.invoke('prometheus:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('prometheus:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('prometheus:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('prometheus:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('prometheus:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('prometheus:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('prometheus:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('prometheus:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('prometheus:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('prometheus:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('prometheus:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('prometheus:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('prometheus:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('prometheus:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('prometheus:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('prometheus:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('prometheus:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('prometheus:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('prometheus:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('prometheus:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('prometheus:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('prometheus:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('prometheus:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('prometheus:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('prometheus:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('prometheus:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('prometheus:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('prometheus:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('prometheus:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('prometheus:keep-awake', on),
  setDisableF12: blocked => ipcRenderer.send('prometheus:devtools:disable-f12', blocked),
  setPreviewShortcutActive: active => ipcRenderer.send('prometheus:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('prometheus:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('prometheus:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('prometheus:preview:reach', url),
  fetchLinkTitle: url => ipcRenderer.invoke('prometheus:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('prometheus:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('prometheus:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('prometheus:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('prometheus:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('prometheus:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('prometheus:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:zoom:changed', listener)

      return () => ipcRenderer.removeListener('prometheus:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('prometheus:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('prometheus:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('prometheus:logs:renderer-error', report),
  readDir: dirPath => ipcRenderer.invoke('prometheus:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('prometheus:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('prometheus:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('prometheus:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('prometheus:fs:desktopPluginsRoot'),
  agentPluginsRoot: () => ipcRenderer.invoke('prometheus:fs:agentPluginsRoot'),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('prometheus:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('prometheus:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('prometheus:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('prometheus:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('prometheus:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('prometheus:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('prometheus:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('prometheus:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('prometheus:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('prometheus:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('prometheus:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('prometheus:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('prometheus:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('prometheus:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('prometheus:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('prometheus:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('prometheus:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('prometheus:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('prometheus:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('prometheus:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('prometheus:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('prometheus:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('prometheus:git:review:prList', repoPath, branches, numbers),
      fetchPrComment: (repoPath, url) => ipcRenderer.invoke('prometheus:git:review:fetchPrComment', repoPath, url),
      createPr: repoPath => ipcRenderer.invoke('prometheus:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('prometheus:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('prometheus:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('prometheus:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('prometheus:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('prometheus:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `prometheus:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `prometheus:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('prometheus:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('prometheus:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('prometheus:preview-nav', listener)

    return () => ipcRenderer.removeListener('prometheus:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('prometheus:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('prometheus:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('prometheus:open-updates', listener)

    return () => ipcRenderer.removeListener('prometheus:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:deep-link', listener)

    return () => ipcRenderer.removeListener('prometheus:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('prometheus:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('prometheus:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('prometheus:plugin:installDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:window-state-changed', listener)

    return () => ipcRenderer.removeListener('prometheus:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('prometheus:focus-session', listener)

    return () => ipcRenderer.removeListener('prometheus:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:notification-action', listener)

    return () => ipcRenderer.removeListener('prometheus:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:notification-activate', listener)

    return () => ipcRenderer.removeListener('prometheus:notification-activate', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('prometheus:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:backend-exit', listener)

    return () => ipcRenderer.removeListener('prometheus:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('prometheus:connection:applied', listener)

    return () => ipcRenderer.removeListener('prometheus:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('prometheus:power-resume', listener)

    return () => ipcRenderer.removeListener('prometheus:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('prometheus:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('prometheus:power-battery', listener)

    return () => ipcRenderer.removeListener('prometheus:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:boot-progress', listener)

    return () => ipcRenderer.removeListener('prometheus:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('prometheus:bootstrap:get'),
  continueBootstrapLocal: () => ipcRenderer.invoke('prometheus:bootstrap:continue-local'),
  resetBootstrap: () => ipcRenderer.invoke('prometheus:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('prometheus:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('prometheus:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('prometheus:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('prometheus:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('prometheus:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('prometheus:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('prometheus:uninstall:summary'),
    run: mode => ipcRenderer.invoke('prometheus:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('prometheus:updates:check'),
    apply: opts => ipcRenderer.invoke('prometheus:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('prometheus:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('prometheus:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('prometheus:updates:progress', listener)

      return () => ipcRenderer.removeListener('prometheus:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('prometheus:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('prometheus:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('prometheus:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('prometheus:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('prometheus:found-in-page', listener)

    return () => ipcRenderer.removeListener('prometheus:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('prometheus:open-find-bar', listener)

    return () => ipcRenderer.removeListener('prometheus:open-find-bar', listener)
  }
})
