(function(){
  const PlatformAdminHooks = {
    async pollJson(endpoint){ const res = await fetch(endpoint, {credentials:'same-origin'}); return await res.json(); },
    renderMetricCards(target, rows){ return {target, kind:'metric_cards', rows}; },
    renderGraph(target, payload){ return {target, kind:'graph', payload}; },
    openDrawer(drawerKey, payload){ return {drawerKey, payload, mode:'drawer'}; },
    openPatchPreview(payload){ return {kind:'patch_preview', payload}; },
    async saveLayout(endpoint, tenantId, layout){
      const res = await fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({tenant_id: tenantId, layout})});
      return await res.json();
    },
    bindDragDrop(workspace){ return {workspace, enabled:true, strategy:'dashboard-grid'}; },
    startLivePolling(endpoint, seconds, onData){
      const intervalMs = Math.max(5, Number(seconds || 15)) * 1000;
      return setInterval(async ()=>{ try { const data = await this.pollJson(endpoint); onData(data); } catch (_) {} }, intervalMs);
    }
  };
  if (typeof window !== 'undefined') { window.PlatformAdminHooks = PlatformAdminHooks; }
})();
