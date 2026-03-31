try { 
    let devices = [];
    let selectedId = null;
    let editingDeviceId = null;
    let editingBasicOnly = false;
    let topologyState = { nodes: [], links: [], version: 1 };
    let view = { x: 0, y: 0, scale: 1 };
    let dragNodeId = null;
    let dragStart = null;
    let panning = false;

    document.addEventListener('DOMContentLoaded', async () => {
      bindEvents();
      await loadDevices();
      await loadTopologyState();
      await loadTopologyTemplates();
      await loadLLM();
      buildTopologyFromDevices();
      renderAll();
    });

    function bindEvents() {
      document.getElementById('btn-add').onclick = openAddDevice;
      document.getElementById('btn-save-device').onclick = saveDevice;
      document.getElementById('btn-save-conn').onclick = saveConnConfig;
      document.getElementById('btn-send').onclick = sendChat;
      document.getElementById('chat-input').onkeydown = e => { if (e.key === 'Enter') sendChat(); };

      document.getElementById('btn-llm').onclick = () => openModal('modal-llm');
      document.getElementById('btn-get-models').onclick = getModels;
      document.getElementById('btn-save-llm').onclick = saveLLM;

      document.getElementById('btn-discover').onclick = discoverTopology;
      document.getElementById('btn-apply').onclick = applyTopology;
      document.getElementById('btn-refresh-facts').onclick = refreshAllFacts;
      document.getElementById('btn-refresh-now').onclick = async () => {
        addMsg('system', '⏳ 重新发现拓扑...');
        try {
          const r = await fetch('/api/topology/discover', { method: 'POST' });
          const d = await r.json();
          if (d.success) {
            topologyState = d.state || topologyState;
            await loadDevices();
            buildTopologyFromDevices();
            await syncTopologyState();
            renderAll();
            addMsg('system', `✅ 发现 ${topologyState.links?.length || 0} 条链路`);
          } else {
            addMsg('system', '❌ 发现失败: ' + (d.message || ''));
          }
        } catch (e) {
          addMsg('system', '❌ 请求失败');
        }
      };
      document.getElementById('topo-autorefresh').onchange = function() {
        if(this.checked) startTopoRefresh(parseInt(document.getElementById('topo-refresh-interval').value));
        else stopTopoRefresh();
      };
      document.getElementById('topo-refresh-interval').onchange = function() {
        if(document.getElementById('topo-autorefresh').checked) startTopoRefresh(parseInt(this.value));
      };
      initTopologyInteractions();
    }

    function openModal(id) { document.getElementById(id).classList.add('show'); }
    function closeModal(id) { document.getElementById(id).classList.remove('show'); }

    function addMsg(type, text) {
      const box = document.getElementById('messages');
      const cls = type === 'user' ? 'msg-user' : (type === 'system' ? 'msg-system' : 'msg-ai');
      box.innerHTML += `<div class="msg ${cls}">${text}</div>`;
      box.scrollTop = box.scrollHeight;
    }

    function toggleFields() {
      const t = document.getElementById('add-type').value;
      document.getElementById('net-fields').style.display = t === 'serial' ? 'none' : 'block';
      document.getElementById('serial-fields').style.display = t === 'serial' ? 'block' : 'none';
      if (t === 'ssh') document.getElementById('add-port').value = '22';
      if (t === 'telnet') document.getElementById('add-port').value = '23';
    }

    function toggleConnFields() {
      const t = document.getElementById('conn-type').value;
      document.getElementById('conn-net-fields').style.display = t === 'serial' ? 'none' : 'block';
      document.getElementById('conn-serial-fields').style.display = t === 'serial' ? 'block' : 'none';
      if (t === 'ssh') document.getElementById('conn-port').value = '22';
      if (t === 'telnet') document.getElementById('conn-port').value = '23';
    }

    function openAddDevice() {
      editingDeviceId = null;
      editingBasicOnly = false;
      document.getElementById('modal-device-title').textContent = '添加设备';
      document.getElementById('add-type').value = 'ssh';
      document.getElementById('add-device-type').value = 'unknown';
      document.getElementById('add-ip').value = '';
      document.getElementById('add-port').value = '22';
      document.getElementById('add-serial').value = '';
      document.getElementById('add-baud').value = '115200';
      document.getElementById('add-remark').value = '';
      document.getElementById('add-user').value = '';
      document.getElementById('add-pass').value = '';
      document.getElementById('add-type').closest('.form-group').style.display = 'block';
      document.getElementById('add-user').closest('.form-group').style.display = 'block';
      document.getElementById('add-pass').closest('.form-group').style.display = 'block';
      toggleFields();
      openModal('modal-device');
    }

    function openDeviceEditor(id) {
      const d = devices.find(x => x.id === id);
      if (!d) return;
      editingDeviceId = id;
      editingBasicOnly = true;
      document.getElementById('modal-device-title').textContent = '编辑设备基础信息（LLM）';
      document.getElementById('add-type').value = d.conn_type || 'ssh';
      toggleFields();
      if (d.conn_type === 'serial') {
        document.getElementById('add-serial').value = d.serial_port || '';
        document.getElementById('add-baud').value = String(d.baud || 115200);
      } else {
        document.getElementById('add-ip').value = d.ip || '';
        document.getElementById('add-port').value = String(d.port || 22);
      }
      document.getElementById('add-device-type').value = d.device_type || 'unknown';
      document.getElementById('add-remark').value = d.remark || '';
      document.getElementById('add-user').value = d.username || '';
      document.getElementById('add-pass').value = d.password || '';

      // 拓扑编辑仅改基础信息，不改连接方式
      document.getElementById('add-type').closest('.form-group').style.display = 'none';
      document.getElementById('net-fields').style.display = 'none';
      document.getElementById('serial-fields').style.display = 'none';
      document.getElementById('add-user').closest('.form-group').style.display = 'none';
      document.getElementById('add-pass').closest('.form-group').style.display = 'none';

      openModal('modal-device');
    }

    function openConnEditor() {
      const d = devices.find(x => x.id === selectedId);
      if (!d) { alert('请先选中设备'); return; }
      document.getElementById('conn-type').value = d.conn_type || 'ssh';
      document.getElementById('conn-ip').value = d.ip || '';
      document.getElementById('conn-port').value = String(d.port || (d.conn_type === 'telnet' ? 23 : 22));
      document.getElementById('conn-serial').value = d.serial_port || '';
      document.getElementById('conn-baud').value = String(d.baud || 115200);
      document.getElementById('conn-user').value = d.username || '';
      document.getElementById('conn-pass').value = d.password || '';
      toggleConnFields();
      openModal('modal-conn');
    }

    async function saveConnConfig() {
      const d = devices.find(x => x.id === selectedId);
      if (!d) { alert('请先选中设备'); return; }
      const connType = document.getElementById('conn-type').value;
      const payload = {
        device_id: d.id,
        conn_type: connType,
        device_type: d.device_type || 'unknown',
        remark: d.remark || '',
        username: document.getElementById('conn-user').value.trim(),
        password: document.getElementById('conn-pass').value,
      };
      if (connType === 'serial') {
        payload.serial_port = document.getElementById('conn-serial').value.trim();
        payload.baud = parseInt(document.getElementById('conn-baud').value || '115200');
        if (!payload.serial_port) { alert('请输入串口'); return; }
      } else {
        payload.ip = document.getElementById('conn-ip').value.trim();
        payload.port = parseInt(document.getElementById('conn-port').value || (connType === 'telnet' ? '23' : '22'));
        if (!payload.ip) { alert('请输入 IP'); return; }
      }

      const r = await fetch('/api/device/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const res = await r.json();
      if (!res.success) { alert(res.message || '保存失败'); return; }
      closeModal('modal-conn');
      await loadDevices();
      buildTopologyFromDevices();
      await syncTopologyState();
      renderAll();
      addMsg('system', '连接方式已更新');
    }

    async function loadDevices() {
      const r = await fetch('/api/devices');
      const d = await r.json();
      devices = d.devices || [];
    }

    async function loadTopologyState() {
      try {
        const r = await fetch('/api/topology/state');
        const d = await r.json();
        topologyState = d.state || { nodes: [], links: [], version: 1 };
      } catch {
        topologyState = { nodes: [], links: [], version: 1 };
      }
    }

    async function syncTopologyState() {
      await fetch('/api/topology/state', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(topologyState)
      });
    }

    function buildTopologyFromDevices() {
      const oldNodes = topologyState.nodes || [];
      topologyState.nodes = devices.map(d => {
        const existing = oldNodes.find(n => n.id === d.id);
        return {
          id: d.id,
          name: d.name,
          remark: d.remark || '',
          ip: d.ip || d.serial_port || 'N/A',
          deviceType: d.device_type || 'unknown',
          x: existing?.x,
          y: existing?.y
        };
      });
    }

    function iconSvg(dtype) {
      const t = (dtype || '').toLowerCase();
      if (t.includes('router')) {
        return `<svg class="node-icon" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="#60a5fa" stroke-width="2"/><path d="M7 12h10M12 7v10" stroke="#60a5fa" stroke-width="2"/></svg>`;
      }
      if (t.includes('firewall')) {
        return `<svg class="node-icon" viewBox="0 0 24 24" fill="none"><rect x="4" y="4" width="16" height="16" rx="2" stroke="#fb923c" stroke-width="2"/><path d="M4 10h16M4 14h16M10 4v16M14 4v16" stroke="#fb923c" stroke-width="1.5"/></svg>`;
      }
      return `<svg class="node-icon" viewBox="0 0 24 24" fill="none"><rect x="3" y="6" width="18" height="12" rx="2" stroke="#34d399" stroke-width="2"/><circle cx="8" cy="12" r="1.5" fill="#34d399"/><circle cx="12" cy="12" r="1.5" fill="#34d399"/><circle cx="16" cy="12" r="1.5" fill="#34d399"/></svg>`;
    }

    function initTopologyInteractions() {
      const infinite = document.getElementById('topology-infinite');
      const nodeLayer = document.getElementById('topology-node-layer');

      infinite.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.08 : 0.08;
        view.scale = Math.min(2.2, Math.max(0.4, view.scale + delta));
        renderTopology();
      }, { passive: false });

      infinite.addEventListener('mousedown', (e) => {
        const node = e.target.closest('.topo-node');
        if (node) {
          dragNodeId = node.dataset.id;
          dragStart = { x: e.clientX, y: e.clientY };
          e.preventDefault();
          return;
        }
        panning = true;
        dragStart = { x: e.clientX, y: e.clientY };
      });

      window.addEventListener('mousemove', (e) => {
        if (dragNodeId) {
          const n = (topologyState.nodes || []).find(x => x.id === dragNodeId);
          if (!n || !dragStart) return;
          n.x += (e.clientX - dragStart.x) / view.scale;
          n.y += (e.clientY - dragStart.y) / view.scale;
          dragStart = { x: e.clientX, y: e.clientY };
          renderTopology();
          return;
        }
        if (panning && dragStart) {
          view.x += (e.clientX - dragStart.x);
          view.y += (e.clientY - dragStart.y);
          dragStart = { x: e.clientX, y: e.clientY };
          renderTopology();
        }
      });

      window.addEventListener('mouseup', async () => {
        if (dragNodeId || panning) {
          dragNodeId = null;
          panning = false;
          dragStart = null;
          await syncTopologyState();
        }
      });
    }

    function renderAll() {
      renderDeviceList();
      renderTopology();
      document.getElementById('device-count').textContent = '设备: ' + devices.length;
    }

    function renderDeviceList() {
      const list = document.getElementById('device-list');
      if (!devices.length) {
        list.innerHTML = '<div style="color:#94a3b8;font-size:12px;">暂无设备</div>';
        return;
      }
      list.innerHTML = devices.map(d => `
        <div class="device-item ${selectedId === d.id ? 'active' : ''}" onclick="openDeviceDetail('${d.id}')">
          <div class="device-name">${d.remark || d.name}</div>
          <div class="device-ip">${d.ip || d.serial_port || 'N/A'}</div>
        </div>
      `).join('');
    }

    function renderTopology() {
      const nodeLayer = document.getElementById('topology-node-layer');
      const svg = document.getElementById('topology-svg');
      const world = document.getElementById('topology-world');

      const nodes = topologyState.nodes || [];
      const links = topologyState.links || [];

      // 无坐标的节点自动排列（网格布局）
      let autoIdx = 0;
      nodes.forEach((n) => {
        if (typeof n.x !== 'number' || typeof n.y !== 'number') {
          const cols = 4;
          const row = Math.floor(autoIdx / cols);
          const col = autoIdx % cols;
          n.x = 40 + col * 200;
          n.y = 40 + row * 140;
          autoIdx++;
        }
      });

      world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;

      if (!nodes.length) {
        nodeLayer.innerHTML = '<div style="color:#94a3b8;position:absolute;left:20px;top:20px;">暂无设备，请先添加设备。</div>';
        svg.innerHTML = '';
      } else {
        nodeLayer.innerHTML = nodes.map(n => {
          const t = (n.deviceType || '').toLowerCase();
          const cls = t.includes('router') ? 'router' : (t.includes('firewall') ? 'firewall' : 'switch');
          const dev = devices.find(x => x.id === n.id);
          const facts = dev?.facts || {};
          let chips = '';
          if (facts.vlan_count) chips += `<span class="chip ok">VLAN:${facts.vlan_count}</span>`;
          if (facts.up_interfaces) chips += `<span class="chip ok">UP:${facts.up_interfaces}</span>`;
          if (facts.trunk_ports?.length) chips += `<span class="chip warn">Trunk:${facts.trunk_ports.length}</span>`;
          chips += facts.last_collected ? `<span class="chip ok">● 在线</span>` : `<span class="chip" style="color:#6b7280;">○ 未采集</span>`;
          return `
          <div class="topo-node ${cls}" data-id="${n.id}" style="left:${n.x}px; top:${n.y}px;" onclick="openTopologyDeviceConfig('${n.id}')">
            <div class="topo-head">${iconSvg(t)}<div class="node-remark">${n.remark || n.name || '未命名设备'}</div></div>
            <div class="node-ip">${n.ip || 'N/A'}</div>
            ${chips ? `<div class="node-chips">${chips}</div>` : ''}
          </div>
        `;
        }).join('');

        svg.innerHTML = links.map((l, idx) => {
          const a = nodes.find(n => n.id === l.from);
          const b = nodes.find(n => n.id === l.to);
          if (!a || !b) return '';

          const pairKey = [l.from, l.to].sort().join('::');
          const siblings = links.filter(x => [x.from, x.to].sort().join('::') === pairKey);
          const order = siblings.findIndex(x => x.id === l.id || x === l);
          const offset = (order - (siblings.length - 1) / 2) * 12;

          const x1 = a.x + 150, y1 = a.y + 32 + offset;
          const x2 = b.x, y2 = b.y + 32 + offset;
          const mid = (x1 + x2) / 2;
          const cls = `topo-edge`;
          const path = `M ${x1} ${y1} L ${mid} ${y1} L ${mid} ${y2} L ${x2} ${y2}`;
          const shortPort = (p) => {
            const s = (p || '?').trim();
            return s
              .replace(/^GigabitEthernet/i, 'GE')
              .replace(/^Ten-GigabitEthernet/i, '10GE')
              .replace(/^FortyGigE/i, '40GE')
              .replace(/^HundredGigE/i, '100GE')
              .replace(/^Ethernet/i, 'Eth');
          };
          const leftPort = shortPort(l.from_port);
          const rightPort = shortPort(l.to_port);
          const cy = (y1 + y2) / 2;
          return `<path class="${cls}" d="${path}" />
                  <text class="port-label" x="${x1 + 8}" y="${y1 - 6}">${leftPort}</text>
                  <text class="port-label right" x="${x2 - 8}" y="${y2 - 6}">${rightPort}</text>`;
        }).join('');
      }

      if (!links.length) {
        // no links yet
      }
    }

    function selectDevice(id) {
      selectedId = id;
      renderAll();
    }

    async function saveDevice() {
      const current = devices.find(x => x.id === editingDeviceId);
      const type = editingBasicOnly && current ? (current.conn_type || 'ssh') : document.getElementById('add-type').value;
      const payload = {
        conn_type: type,
        device_type: document.getElementById('add-device-type').value,
        remark: document.getElementById('add-remark').value.trim(),
        username: editingBasicOnly && current ? (current.username || '') : document.getElementById('add-user').value.trim(),
        password: editingBasicOnly && current ? (current.password || '') : document.getElementById('add-pass').value
      };
      if (editingBasicOnly && editingDeviceId) {
        payload.device_id = editingDeviceId;
        payload.basic_only = true;
      }

      if (type === 'serial') {
        payload.serial_port = editingBasicOnly && current ? (current.serial_port || '') : document.getElementById('add-serial').value.trim();
        payload.baud = editingBasicOnly && current ? parseInt(current.baud || 115200) : parseInt(document.getElementById('add-baud').value || '115200');
      } else {
        payload.ip = editingBasicOnly && current ? (current.ip || '') : document.getElementById('add-ip').value.trim();
        payload.port = editingBasicOnly && current ? parseInt(current.port || (type === 'telnet' ? 23 : 22)) : parseInt(document.getElementById('add-port').value || (type === 'telnet' ? '23' : '22'));
        if (!payload.ip) { alert('请输入 IP'); return; }
      }

      const r = await fetch('/api/device/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      if (!d.success) { alert(d.message || '保存失败'); return; }

      closeModal('modal-device');
      await loadDevices();
      buildTopologyFromDevices();
      await syncTopologyState();
      renderAll();
      addMsg('system', editingDeviceId ? '设备已更新' : '设备已保存');
      editingDeviceId = null;
      editingBasicOnly = false;
    }


    async function loadTopologyTemplates() { /* placeholder */ }
    async function saveTopologyTemplate() { /* placeholder */ }
    async function loadTopologyTemplate() { /* placeholder */ }

    async function discoverTopology() {
      const r = await fetch('/api/topology/discover', { method: 'POST' });
      const d = await r.json();
      if (!d.success) { alert(d.message || '识别失败'); return; }
      topologyState = d.state || topologyState;
      renderTopology();
      addMsg('system', `拓扑识别完成，发现 ${d.discovered_links || 0} 条连线`);
    }

    async function applyTopology() {
      const r = await fetch('/api/topology/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: topologyState })
      });
      const d = await r.json();
      if (!d.success) { alert(d.message || '应用失败'); return; }
      const ok = (d.results || []).filter(x => x.result && x.result.success).length;
      const total = (d.results || []).length;
      addMsg('system', `拓扑应用完成：${ok}/${total} 成功`);
    }

    async function loadLLM() {
      try {
        const r = await fetch('/api/llm/config');
        const d = await r.json();
        if (d.endpoint) {
          document.getElementById('llm-endpoint').value = d.endpoint;
          document.getElementById('llm-key').value = d.api_key || '';
          if (d.model) document.getElementById('llm-model').innerHTML = `<option value="${d.model}">${d.model}</option>`;
          document.getElementById('llm-status').textContent = 'LLM: ' + (d.model || '已配置');
        }
      } catch {}
    }

    async function getModels() {
      const endpoint = document.getElementById('llm-endpoint').value.trim();
      const api_key = document.getElementById('llm-key').value.trim();
      if (!endpoint) { alert('请输入 Endpoint'); return; }
      const r = await fetch('/api/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint, api_key })
      });
      const d = await r.json();
      if (!d.success || !(d.models || []).length) { alert(d.message || '获取失败'); return; }
      document.getElementById('llm-model').innerHTML = d.models.map(m => `<option value="${m}">${m}</option>`).join('');
    }

    async function saveLLM() {
      const payload = {
        provider: 'openai',
        endpoint: document.getElementById('llm-endpoint').value.trim(),
        api_key: document.getElementById('llm-key').value.trim(),
        model: document.getElementById('llm-model').value
      };
      if (!payload.endpoint) { alert('请输入 Endpoint'); return; }
      const r = await fetch('/api/llm/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      if (!d.success) { alert(d.message || '保存失败'); return; }
      closeModal('modal-llm');
      document.getElementById('llm-status').textContent = 'LLM: ' + (payload.model || '已配置');
      addMsg('system', 'LLM 配置已保存');
    }

    async function sendChat() {
      const input = document.getElementById('chat-input');
      const msg = input.value.trim();
      if (!msg) return;
      addMsg('user', msg);
      input.value = '';
      const d = devices.find(x => x.id === selectedId);
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, context: { selected_device: d?.name || d?.remark } })
      });
      const res = await r.json();
      addMsg('ai', (res.executed ? '✅ ' : '') + (res.response || '无响应'));
    }

    // ===== 设备详情弹窗 =====
    function openDeviceDetail(id) {
      selectedId = id;
      renderAll();
      const d = devices.find(x => x.id === id);
      if (!d) return;
      document.getElementById('detail-modal-title').textContent = d.remark || d.name;
      const box = document.getElementById('detail-content');
      const fields = [
        ['名称',d.name],['备注',d.remark||'-'],['IP',d.ip||'-'],['端口',d.port||d.serial_port||'-'],
        ['连接方式',d.conn_type||'-'],['厂商',d.vendor||'-'],['型号',d.model||'-'],['版本',d.os_version||'-'],['用户名',d.username||'-']
      ];
      let html = fields.map(f => `<div class="detail-row"><div class="detail-key">${f[0]}</div><div class="detail-val">${f[1]}</div></div>`).join('');
      const facts = d.facts||{};
      if (facts.last_collected) {
        html += '<div style="margin-top:8px;font-size:11px;color:#6b7280;">状态信息</div>';
        [['VLAN数',facts.vlan_count],['UP接口',facts.up_interfaces],['总接口',facts.total_interfaces],['Trunk端口',(facts.trunk_ports||[]).join(', ')],['最后采集',facts.last_collected]].forEach(f => html += `<div class="detail-row"><div class="detail-key">${f[0]}</div><div class="detail-val">${f[1]||'-'}</div></div>`);
      }
      box.innerHTML = html;
      document.getElementById('btn-test-detail').onclick = async () => {
        const dd = devices.find(x => x.id === id);
        if (!dd) return;
        closeModal('modal-device-detail');
        addMsg('system', `测试连接 ${dd.remark || dd.name}...`);
        const r = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:`测试设备 ${dd.remark||dd.name} 的连通性`,context:{selected_device:dd.name||dd.remark}})});
        const res = await r.json();
        addMsg('ai', (res.success?'✅ ':'❌ ')+(res.response||res.message||''));
      };
      document.getElementById('btn-conn-edit-detail').onclick = () => { closeModal('modal-device-detail'); openDeviceEditor(d.id); };
      document.getElementById('btn-delete-detail').onclick = async () => {
        if (!confirm('确认删除设备?')) return;
        closeModal('modal-device-detail');
        const r = await fetch('/api/device/delete', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device_id:d.id})});
        const res = await r.json();
        if (res.success) { selectedId=null; await loadDevices(); buildTopologyFromDevices(); await syncTopologyState(); renderAll(); addMsg('system','✅ 已删除'); }
        else addMsg('system','❌ '+res.message);
      };
      openModal('modal-device-detail');
    }

    // ===== 配置中心（拓扑节点点击弹出） =====

    function openTopologyDeviceConfig(id) {
      selectedId = id;
      renderAll();
      renderConfigPanel();
      openModal('modal-config');
    }

    let _cfgTab = '查看';
    let _cfgDevice = '';

    function renderConfigPanel() {
      const d = devices.find(x => x.id === selectedId);
      if (!d) return;
      _cfgDevice = d.remark || d.name;
      const dtype = (d.device_type || '').toLowerCase();
      const isL2 = dtype.includes('layer2') || (dtype.includes('switch') && !dtype.includes('layer3'));
      const isL3Sw = dtype.includes('layer3');
      const isR = dtype.includes('router');
      const isFw = dtype.includes('firewall');
      const isL3 = isL3Sw || isR || isFw;
      const isSw = isL2 || isL3Sw;
      const facts = d.facts || {};
      const typeMap = {layer2_switch:'二层交换机',layer3_switch:'三层交换机',router:'路由器',firewall:'防火墙',unknown:'未识别'};
      const vendorMap = {huawei:'华为',h3c:'H3C',cisco:'思科',ruijie:'锐捷',juniper:'Juniper'};
      const tl = typeMap[dtype]||dtype; const vl = vendorMap[(d.vendor||'').toLowerCase()]||d.vendor||'未知';

      let thtml = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <span style="color:#67e8f9;font-size:14px;font-weight:700;">${_cfgDevice}</span>
        <span style="font-size:11px;padding:2px 8px;border-radius:4px;background:#1e293b;color:#94a3b8;">${tl} · ${vl}</span>
      </div>`;
      if(facts.last_collected){
        thtml+=`<div style="font-size:11px;color:#6b7280;margin-bottom:6px;">`;
        if(facts.vlan_count) thtml+=`VLAN:${facts.vlan_count} `;
        if(facts.up_interfaces) thtml+=`UP:${facts.up_interfaces}/${facts.total_interfaces||'?'} `;
        if(facts.trunk_ports?.length) thtml+=`Trunk:${facts.trunk_ports.length} `;
        thtml+=`</div>`;
      }

      // 构建 tab 列表
      let tabs = [{k:'查看',l:'📋 查看'},{k:'VLAN',l:'🏷 VLAN'},{k:'接口',l:'🔌 接口'},{k:'端口模式',l:'🔗 端口模式'}];
      if(isL3) tabs.push({k:'L3路由',l:'🌐 L3路由'});
      if(isR||isFw) tabs.push({k:'安全策略',l:'🛡 安全策略'});
      tabs.push({k:'系统',l:'⚙ 系统'});
      tabs.push({k:'诊断',l:'🔍 诊断'});

      thtml += `<div style="display:flex;gap:0;border-bottom:1px solid #1f2937;margin-bottom:8px;overflow-x:auto;">`;
      tabs.forEach(t => {
        thtml += `<button class="cfg-tab${_cfgTab===t.k?' active':''}" data-tab="${t.k}" onclick="switchCfgTab('${t.k}')">${t.l}</button>`;
      });
      thtml += `</div>`;
      thtml += `<div id="cfg-tab-content"></div>`;

      document.getElementById('config-tabs').style.display = 'none';
      document.getElementById('config-panel').innerHTML = thtml;
      switchCfgTab(_cfgTab);
    }

    function switchCfgTab(tab) {
      _cfgTab = tab;
      document.querySelectorAll('.cfg-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
      const el = document.getElementById('cfg-tab-content');
      const d = devices.find(x => x.id === selectedId);
      const dtype = (d?.device_type || '').toLowerCase();
      const isL3 = dtype.includes('layer3')||dtype.includes('router')||dtype.includes('firewall');
      const dev = _cfgDevice;
      switch(tab) {
        case '查看': el.innerHTML = buildTabView(dev); break;
        case 'VLAN': el.innerHTML = buildTabVlan(dev); break;
        case '接口': el.innerHTML = buildTabInterface(dev); break;
        case '端口模式': el.innerHTML = buildTabPortMode(dev); break;
        case 'L3路由': el.innerHTML = isL3 ? buildTabL3(dev) : '<div style="color:#94a3b8;font-size:12px;">此设备不支持三层配置</div>'; break;
        case '安全策略': el.innerHTML = buildTabSecurity(dev); break;
        case '系统': el.innerHTML = buildTabSystem(dev); break;
        case '诊断': el.innerHTML = buildTabDiag(dev); break;
      }
    }

    // ===== Tab: 查看 =====
    function buildTabView(dev) {
      const btns = [
        ['当前配置','查看 running-config'],['VLAN 信息','查看所有 VLAN 信息'],['VLAN Brief','查看 VLAN 简要信息'],
        ['接口状态','查看接口状态'],['接口简要','查看接口简要信息'],['接口计数','查看接口计数器/流量统计'],
        ['路由表','查看路由表'],['ARP 表','查看 ARP 表'],['MAC 地址表','查看 MAC 地址表'],
        ['LLDP 邻居','查看 LLDP 邻居'],['CDP 邻居','查看 CDP 邻居'],['STP 状态','查看 STP 生成树状态'],
        ['设备信息','查看设备基本信息'],['版本信息','查看设备版本'],['系统时间','查看系统时间'],
        ['CPU 利用率','查看 CPU 利用率'],['内存使用','查看内存使用率'],['日志','查看最近日志'],
        ['告警信息','查看告警信息'],['环境温度','查看设备温度/环境信息'],
        ['风扇状态','查看风扇状态'],['电源状态','查看电源状态'],
        ['NAT 会话','查看 NAT 会话表'],['OSPF 邻居','查看 OSPF 邻居'],['BGP 邻居','查看 BGP 邻居'],
      ];
      let h = `<div class="cfg-grid">`;
      btns.forEach(b => { h += `<button class="btn" onclick="quickQuery('${dev}','${b[1]}')">${b[0]}</button>`; });
      h += `</div>`;
      h += `<div style="margin-top:8px;"><button class="config-exec-btn" style="background:#064e3b;" onclick="collectDeviceFacts('${dev}');addMsg('system','✅ 状态已采集');">🔄 采集设备状态</button></div>`;
      h += `<div id="cfg-query-result" class="config-result" style="display:none;"></div>`;
      return h;
    }

    // ===== Tab: VLAN =====
    function buildTabVlan(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">创建 / 删除 VLAN</h4>
          <div class="form-group"><label>操作</label><select id="cfg-vlan-action"><option value="create">创建</option><option value="delete">删除</option></select></div>
          <div class="form-group"><label>VLAN ID</label><input id="cfg-vlan-id" placeholder="10 或 10,20,30"></div>
          <div class="form-group"><label>VLAN 名称</label><input id="cfg-vlan-name" placeholder="财务部"></div>
          <div class="form-group"><label>VLAN 描述（可选）</label><input id="cfg-vlan-desc" placeholder="描述信息"></div>
          <button class="config-exec-btn" onclick="execForm('vlan','${dev}')">执行</button>
          <div id="cfg-vlan-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">批量 VLAN</h4>
          <div class="form-group"><label>批量创建（每行一个：VLAN ID 名称）</label><textarea id="cfg-vlan-batch" rows="6" style="width:100%;background:#0b1220;color:#e5e7eb;border:1px solid #334155;border-radius:6px;padding:6px;font-size:12px;" placeholder="10 财务部&#10;20 人事部&#10;30 技术部"></textarea></div>
          <button class="config-exec-btn" onclick="execBatchVlan('${dev}')">批量创建</button>
          <div id="cfg-vlan-batch-result" class="config-result" style="display:none;"></div>
        </div>
      </div>`;
    }

    // ===== Tab: 接口 =====
    function buildTabInterface(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">接口操作</h4>
          <div class="form-group"><label>接口</label><input id="cfg-if-port" placeholder="GE0/0/1 或范围 1-4"></div>
          <div class="form-group"><label>操作</label>
            <select id="cfg-if-action"><option value="desc">设置描述</option><option value="shutdown">关闭</option><option value="noshutdown">开启</option><option value="speed">设置速率</option><option value="duplex">设置双工</option></select>
          </div>
          <div class="form-group"><label>参数值</label><input id="cfg-if-val" placeholder="描述文字 / 速率 / 双工模式"></div>
          <button class="config-exec-btn" onclick="execForm('interface','${dev}')">执行</button>
          <div id="cfg-if-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">批量操作</h4>
          <div class="form-group"><label>接口范围</label><input id="cfg-if-range" placeholder="GE0/0/1 到 GE0/0/24"></div>
          <div class="form-group"><label>批量操作</label>
            <select id="cfg-if-batch-action"><option value="shutdown">批量关闭</option><option value="noshutdown">批量开启</option><option value="desc">批量设置描述</option></select>
          </div>
          <div class="form-group"><label>描述（可选）</label><input id="cfg-if-batch-desc" placeholder="统一描述"></div>
          <button class="config-exec-btn" onclick="execForm('interface-batch','${dev}')">批量执行</button>
          <div id="cfg-if-batch-result" class="config-result" style="display:none;"></div>
        </div>
      </div>`;
    }

    // ===== Tab: 端口模式 =====
    function buildTabPortMode(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">Access / Trunk</h4>
          <div class="form-group"><label>接口</label><input id="cfg-pm-port" placeholder="GE0/0/1"></div>
          <div class="form-group"><label>模式</label><select id="cfg-pm-mode"><option value="access">Access</option><option value="trunk">Trunk</option></select></div>
          <div class="form-group"><label>VLAN ID</label><input id="cfg-pm-vlan" placeholder="Access 填 VLAN ID"></div>
          <div class="form-group"><label>允许 VLAN（Trunk）</label><input id="cfg-pm-allow" placeholder="10,20,30 或 all"></div>
          <div class="form-group"><label>Native VLAN（Trunk，可选）</label><input id="cfg-pm-native" placeholder="默认 VLAN"></div>
          <button class="config-exec-btn" onclick="execForm('portmode','${dev}')">执行</button>
          <div id="cfg-pm-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">端口聚合 / 镜像</h4>
          <div class="form-group"><label>类型</label><select id="cfg-pm-special"><option value="agg-lacp">聚合(LACP)</option><option value="agg-static">聚合(静态)</option><option value="mirror-src">镜像源</option><option value="mirror-dst">镜像目的</option></select></div>
          <div class="form-group"><label>接口</label><input id="cfg-pm-sp-port" placeholder="GE0/0/1,GE0/0/2"></div>
          <div class="form-group"><label>聚合组/会话号</label><input id="cfg-pm-sp-group" placeholder="1"></div>
          <button class="config-exec-btn" onclick="execForm('portspecial','${dev}')">执行</button>
          <div id="cfg-pm-sp-result" class="config-result" style="display:none;"></div>
        </div>
      </div>`;
    }

    // ===== Tab: L3 路由 =====
    function buildTabL3(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">SVI / 接口 IP</h4>
          <div class="form-group"><label>类型</label><select id="cfg-l3-iftype"><option value="svi">VLAN 接口</option><option value="phy">物理接口 IP</option><option value="loopback">Loopback</option></select></div>
          <div class="form-group"><label>接口/VLAN</label><input id="cfg-l3-iface" placeholder="VLAN 10 或 GE0/0/1"></div>
          <div class="form-group"><label>IP 地址</label><input id="cfg-l3-ip" placeholder="192.168.10.1/24"></div>
          <button class="config-exec-btn" onclick="execForm('l3-if','${dev}')">执行</button>
          <div id="cfg-l3-if-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">静态路由</h4>
          <div class="form-group"><label>目标网段</label><input id="cfg-l3-rt-dst" placeholder="0.0.0.0/0"></div>
          <div class="form-group"><label>下一跳 / 出接口</label><input id="cfg-l3-rt-nh" placeholder="10.0.0.2 或 GE0/0/1"></div>
          <div class="form-group"><label>优先级（可选）</label><input id="cfg-l3-rt-pref" placeholder="默认 60"></div>
          <button class="config-exec-btn" onclick="execForm('l3-route','${dev}')">执行</button>
          <div id="cfg-l3-rt-result" class="config-result" style="display:none;"></div>
        </div>
      </div>
      <div style="margin-top:8px;">
        <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">动态路由协议</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
          <div>
            <h5 style="color:#94a3b8;font-size:12px;">OSPF</h5>
            <div class="form-group"><label>进程号</label><input id="cfg-l3-ospf-id" placeholder="1"></div>
            <div class="form-group"><label>宣告网段</label><input id="cfg-l3-ospf-net" placeholder="192.168.0.0/16 area 0"></div>
            <button class="config-exec-btn" onclick="execForm('l3-ospf','${dev}')">配置 OSPF</button>
            <div id="cfg-l3-ospf-result" class="config-result" style="display:none;"></div>
          </div>
          <div>
            <h5 style="color:#94a3b8;font-size:12px;">BGP</h5>
            <div class="form-group"><label>AS 号</label><input id="cfg-l3-bgp-as" placeholder="65000"></div>
            <div class="form-group"><label>邻居</label><input id="cfg-l3-bgp-nbr" placeholder="10.0.0.2 AS 65001"></div>
            <button class="config-exec-btn" onclick="execForm('l3-bgp','${dev}')">配置 BGP</button>
            <div id="cfg-l3-bgp-result" class="config-result" style="display:none;"></div>
          </div>
          <div>
            <h5 style="color:#94a3b8;font-size:12px;">DHCP</h5>
            <div class="form-group"><label>地址池名</label><input id="cfg-l3-dhcp-pool" placeholder="pool1"></div>
            <div class="form-group"><label>网段/网关</label><input id="cfg-l3-dhcp-net" placeholder="192.168.1.0/24 GW 192.168.1.1"></div>
            <button class="config-exec-btn" onclick="execForm('l3-dhcp','${dev}')">配置 DHCP</button>
            <div id="cfg-l3-dhcp-result" class="config-result" style="display:none;"></div>
          </div>
        </div>
      </div>`;
    }

    // ===== Tab: 安全策略 =====
    function buildTabSecurity(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">ACL / 过滤</h4>
          <div class="form-group"><label>操作</label><select id="cfg-sec-acl-act"><option value="create">创建</option><option value="delete">删除</option></select></div>
          <div class="form-group"><label>规则编号</label><input id="cfg-sec-acl-id" placeholder="10"></div>
          <div class="form-group"><label>动作</label><select id="cfg-sec-acl-perm"><option value="permit">permit</option><option value="deny">deny</option></select></div>
          <div class="form-group"><label>源</label><input id="cfg-sec-acl-src" placeholder="192.168.1.0/24"></div>
          <div class="form-group"><label>目标</label><input id="cfg-sec-acl-dst" placeholder="any"></div>
          <div class="form-group"><label>协议/端口（可选）</label><input id="cfg-sec-acl-proto" placeholder="tcp eq 80"></div>
          <div class="form-group"><label>应用到接口</label><input id="cfg-sec-acl-if" placeholder="GE0/0/1 inbound"></div>
          <button class="config-exec-btn" onclick="execForm('acl','${dev}')">执行</button>
          <div id="cfg-sec-acl-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">NAT</h4>
          <div class="form-group"><label>类型</label><select id="cfg-sec-nat-type"><option value="snat">源 NAT(SNAT/PAT)</option><option value="dnat">目的 NAT(DNAT)</option></select></div>
          <div class="form-group"><label>源/内部地址</label><input id="cfg-sec-nat-src" placeholder="192.168.1.0/24"></div>
          <div class="form-group"><label>外部接口/IP</label><input id="cfg-sec-nat-ext" placeholder="GE0/0/1 或 202.1.1.1"></div>
          <div class="form-group"><label>端口映射（DNAT）</label><input id="cfg-sec-nat-port" placeholder="8080→80"></div>
          <button class="config-exec-btn" onclick="execForm('nat','${dev}')">执行</button>
          <div id="cfg-sec-nat-result" class="config-result" style="display:none;"></div>
          <h4 style="color:#67e8f9;font-size:13px;margin:12px 0 6px;">安全域/Zone</h4>
          <div class="form-group"><label>操作</label><select id="cfg-sec-zone-act"><option value="create">创建安全域</option><option value="addif">添加接口</option><option value="policy">域间策略</option></select></div>
          <div class="form-group"><label>域名</label><input id="cfg-sec-zone-name" placeholder="Trust"></div>
          <div class="form-group"><label>接口/策略</label><input id="cfg-sec-zone-val" placeholder="GE0/0/1 或策略描述"></div>
          <button class="config-exec-btn" onclick="execForm('zone','${dev}')">执行</button>
          <div id="cfg-sec-zone-result" class="config-result" style="display:none;"></div>
        </div>
      </div>`;
    }

    // ===== Tab: 系统 =====
    function buildTabSystem(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">设备管理</h4>
          <div class="form-group"><label>设备名称</label><input id="cfg-sys-name" placeholder="SW-Core-01"></div>
          <button class="config-exec-btn" onclick="execForm('sys-name','${dev}')">设置名称</button>
          <div class="form-group" style="margin-top:8px;"><label>管理 IP / 网关</label><input id="cfg-sys-mgmt" placeholder="192.168.1.1/24 GW 192.168.1.254"></div>
          <button class="config-exec-btn" onclick="execForm('sys-mgmt','${dev}')">设置管理 IP</button>
          <div id="cfg-sys-basic-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">密码 / 远程</h4>
          <div class="form-group"><label>操作</label>
            <select id="cfg-sys-sec-act"><option value="passwd">设置 Console 密码</option><option value="ssh">启用 SSH</option><option value="telnet">启用 Telnet</option><option value="acl-remote">限制远程访问 IP</option></select>
          </div>
          <div class="form-group"><label>参数</label><input id="cfg-sys-sec-val" placeholder="密码 / ACL / IP 列表"></div>
          <button class="config-exec-btn" onclick="execForm('sys-sec','${dev}')">执行</button>
          <div id="cfg-sys-sec-result" class="config-result" style="display:none;"></div>
        </div>
      </div>
      <div style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;">
        <button class="config-exec-btn" style="background:#065f46;" onclick="quickQuery('${dev}','保存配置')">💾 保存配置</button>
        <button class="config-exec-btn" style="background:#7c2d12;" onclick="quickQuery('${dev}','查看当前配置和启动配置差异')">⚠ 查看配置差异</button>
        <button class="config-exec-btn" style="background:#1e293b;" onclick="quickQuery('${dev}','导出当前配置')">📤 导出配置</button>
      </div>`;
    }

    // ===== Tab: 诊断 =====
    function buildTabDiag(dev) {
      return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">连通性测试</h4>
          <div class="form-group"><label>目标 IP</label><input id="cfg-dg-ping" placeholder="192.168.1.1"></div>
          <div class="form-group"><label>次数</label><input id="cfg-dg-ping-c" placeholder="5" value="5"></div>
          <button class="config-exec-btn" onclick="execForm('ping','${dev}')">Ping</button>
          <div id="cfg-dg-ping-result" class="config-result" style="display:none;"></div>
          <div class="form-group" style="margin-top:8px;"><label>Traceroute 目标</label><input id="cfg-dg-trace" placeholder="10.0.0.1"></div>
          <button class="config-exec-btn" onclick="execForm('traceroute','${dev}')">Traceroute</button>
          <div id="cfg-dg-trace-result" class="config-result" style="display:none;"></div>
        </div>
        <div>
          <h4 style="color:#67e8f9;font-size:13px;margin-bottom:6px;">诊断工具</h4>
          <div class="cfg-grid">
            <button class="btn" onclick="quickQuery('${dev}','诊断 VLAN 配置问题')">诊断 VLAN</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断接口故障')">诊断接口</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断路由问题')">诊断路由</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断 ARP 问题')">诊断 ARP</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断 STP 问题')">诊断 STP</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断 ACL 是否生效')">诊断 ACL</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断 NAT 问题')">诊断 NAT</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断 OSPF 邻居关系')">诊断 OSPF</button>
            <button class="btn" onclick="quickQuery('${dev}','诊断 BGP 问题')">诊断 BGP</button>
            <button class="btn" onclick="quickQuery('${dev}','综合健康检查')">综合检查</button>
          </div>
          <div id="cfg-dg-tool-result" class="config-result" style="display:none;"></div>
        </div>
      </div>`;
    }

    // ===== 统一执行 =====
    function execForm(type, dev) {
      const v = id => { const e = document.getElementById(id); return e ? e.value.trim() : ''; };
      let msg = '';
      switch(type) {
        case 'vlan': {
          const act=v('cfg-vlan-action'), vid=v('cfg-vlan-id'), nm=v('cfg-vlan-name'), desc=v('cfg-vlan-desc');
          if(!vid){alert('填 VLAN ID');return;}
          msg = act==='create' ? `在 ${dev} 上创建 VLAN ${vid}${nm?' 名称 '+nm:''}${desc?' 描述 '+desc:''}` : `在 ${dev} 上删除 VLAN ${vid}`;
          break;
        }
        case 'interface': {
          const port=v('cfg-if-port'), act=v('cfg-if-action'), val=v('cfg-if-val');
          if(!port){alert('填接口');return;}
          if(act==='desc') msg=`在 ${dev} 上给接口 ${port} 设置描述"${val}"`;
          else if(act==='shutdown') msg=`在 ${dev} 上关闭接口 ${port}`;
          else if(act==='noshutdown') msg=`在 ${dev} 上开启接口 ${port}`;
          else if(act==='speed') msg=`在 ${dev} 上将接口 ${port} 速率设为 ${val||'auto'}`;
          else if(act==='duplex') msg=`在 ${dev} 上将接口 ${port} 双工模式设为 ${val||'auto'}`;
          break;
        }
        case 'interface-batch': {
          const range=v('cfg-if-range'), act=v('cfg-if-batch-action'), desc=v('cfg-if-batch-desc');
          if(!range){alert('填接口范围');return;}
          const actMap={shutdown:'关闭',noshutdown:'开启',desc:'设置描述'};
          msg=`在 ${dev} 上对接口 ${range} 批量${actMap[act]||act}`;
          if(desc) msg+=`，描述"${desc}"`;
          break;
        }
        case 'portmode': {
          const port=v('cfg-pm-port'), mode=v('cfg-pm-mode'), vlan=v('cfg-pm-vlan'), allow=v('cfg-pm-allow'), native=v('cfg-pm-native');
          if(!port){alert('填接口');return;}
          if(mode==='access') msg=`在 ${dev} 上将接口 ${port} 设为 Access，VLAN ${vlan||'?'}`;
          else { msg=`在 ${dev} 上将接口 ${port} 设为 Trunk`; if(allow) msg+=`，允许 VLAN ${allow}`; if(native) msg+=`，Native VLAN ${native}`; if(vlan) msg+=`，默认 VLAN ${vlan}`; }
          break;
        }
        case 'portspecial': {
          const sp=v('cfg-pm-special'), port=v('cfg-pm-sp-port'), grp=v('cfg-pm-sp-group');
          if(!port||!grp){alert('填接口和组号');return;}
          const map={'agg-lacp':'配置 LACP 端口聚合','agg-static':'配置静态端口聚合','mirror-src':'配置镜像源端口','mirror-dst':'配置镜像目的端口'};
          msg=`在 ${dev} 上${map[sp]||sp}，接口 ${port}，组号 ${grp}`;
          break;
        }
        case 'l3-if': {
          const ft=v('cfg-l3-iftype'), iface=v('cfg-l3-iface'), ip=v('cfg-l3-ip');
          if(!iface||!ip){alert('填接口和 IP');return;}
          const map={svi:'VLAN 接口',phy:'物理接口',loopback:'Loopback'};
          msg=`在 ${dev} 上配置${map[ft]||ft} ${iface}，IP ${ip}`;
          break;
        }
        case 'l3-route': {
          const dst=v('cfg-l3-rt-dst'), nh=v('cfg-l3-rt-nh'), pref=v('cfg-l3-rt-pref');
          if(!dst||!nh){alert('填目标和下一跳');return;}
          msg=`在 ${dev} 上配置静态路由，目标 ${dst}，下一跳 ${nh}`;
          if(pref) msg+=`，优先级 ${pref}`;
          break;
        }
        case 'l3-ospf': {
          const id=v('cfg-l3-ospf-id'), net=v('cfg-l3-ospf-net');
          if(!net){alert('填网段');return;}
          msg=`在 ${dev} 上配置 OSPF 进程 ${id||'1'}，宣告 ${net}`;
          break;
        }
        case 'l3-bgp': {
          const as=v('cfg-l3-bgp-as'), nbr=v('cfg-l3-bgp-nbr');
          if(!as){alert('填 AS 号');return;}
          msg=`在 ${dev} 上配置 BGP AS ${as}`; if(nbr) msg+=`，邻居 ${nbr}`;
          break;
        }
        case 'l3-dhcp': {
          const pool=v('cfg-l3-dhcp-pool'), net=v('cfg-l3-dhcp-net');
          if(!pool||!net){alert('填地址池和网段');return;}
          msg=`在 ${dev} 上配置 DHCP 地址池 ${pool}，${net}`;
          break;
        }
        case 'acl': {
          const act=v('cfg-sec-acl-act'), rid=v('cfg-sec-acl-id'), perm=v('cfg-sec-acl-perm'), src=v('cfg-sec-acl-src'), dst=v('cfg-sec-acl-dst'), proto=v('cfg-sec-acl-proto'), iface=v('cfg-sec-acl-if');
          if(act==='delete'){if(!rid){alert('填规则号');return;} msg=`在 ${dev} 上删除 ACL 规则 ${rid}`; break;}
          if(!src&&!dst){alert('填源或目标');return;}
          msg=`在 ${dev} 上创建 ACL 规则 ${rid||'自动'}，${perm} ${src||'any'} → ${dst||'any'}`;
          if(proto) msg+=` ${proto}`; if(iface) msg+=`，应用到 ${iface}`;
          break;
        }
        case 'nat': {
          const nt=v('cfg-sec-nat-type'), src=v('cfg-sec-nat-src'), ext=v('cfg-sec-nat-ext'), port=v('cfg-sec-nat-port');
          if(!src||!ext){alert('填内部地址和外部信息');return;}
          if(nt==='snat') msg=`在 ${dev} 上配置源 NAT，${src} 经 ${ext} 转换`;
          else msg=`在 ${dev} 上配置目的 NAT，外部 ${ext}→${src}${port?' 端口 '+port:''}`;
          break;
        }
        case 'zone': {
          const act=v('cfg-sec-zone-act'), nm=v('cfg-sec-zone-name'), val=v('cfg-sec-zone-val');
          if(!nm){alert('填域名');return;}
          const map={create:'创建安全域',addif:'将 '+val+' 加入安全域',policy:'配置域间策略'};
          msg=`在 ${dev} 上${map[act]||act} ${nm}`; if(act==='policy') msg+=`：${val}`;
          break;
        }
        case 'sys-name': { const nm=v('cfg-sys-name'); if(!nm){alert('填名称');return;} msg=`在 ${dev} 上设置设备名称为 ${nm}`; break; }
        case 'sys-mgmt': { const mg=v('cfg-sys-mgmt'); if(!mg){alert('填管理 IP');return;} msg=`在 ${dev} 上配置管理地址 ${mg}`; break; }
        case 'sys-sec': {
          const act=v('cfg-sys-sec-act'), val=v('cfg-sys-sec-val');
          const map={passwd:'设置 Console 密码',ssh:'启用 SSH 远程管理',telnet:'启用 Telnet 远程管理','acl-remote':'限制远程访问 IP 为 '+val};
          msg=`在 ${dev} 上${map[act]||act}${act==='passwd'?' 密码 '+val:''}`;
          break;
        }
        case 'ping': { const ip=v('cfg-dg-ping'), c=v('cfg-dg-ping-c'); if(!ip){alert('填目标 IP');return;} msg=`在 ${dev} 上 ping ${ip}，次数 ${c||5}`; break; }
        case 'traceroute': { const ip=v('cfg-dg-trace'); if(!ip){alert('填目标');return;} msg=`在 ${dev} 上 traceroute ${ip}`; break; }
      }
      if(!msg) return;
      const resultId = `cfg-${type}-result`;
      doExec(dev, msg, resultId);
    }

    function execBatchVlan(dev) {
      const text = document.getElementById('cfg-vlan-batch').value.trim();
      if(!text){alert('填 VLAN 列表');return;}
      const lines = text.split('\n').filter(l=>l.trim());
      const vlans = lines.map(l => { const p=l.trim().split(/\s+/); return p[0] + (p[1]?' 名称 '+p[1]:''); }).join('、');
      doExec(dev, `在 ${dev} 上批量创建 VLAN：${vlans}`, 'cfg-vlan-batch-result');
    }

    async function doExec(dev, msg, resultId) {
      addMsg('user', msg);
      const el = document.getElementById(resultId);
      if(el){el.style.display='block';el.className='config-result';el.textContent='⏳ 执行中...';}
      const d = devices.find(x => x.id === selectedId);
      try {
        const r = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,context:{selected_device:d?.name||d?.remark}})});
        const res = await r.json();
        if(el){
          el.className = res.success ? 'config-result success' : 'config-result error';
          el.textContent = res.response || res.message || (res.success?'成功':'失败');
        }
        addMsg('ai', (res.success?'✅ ':'❌ ')+(res.response||res.message||''));
        if(res.success) collectDeviceFacts(d?.name||d?.remark);
      } catch(e) {
        if(el){el.className='config-result error';el.textContent='请求失败';}
        addMsg('ai','❌ 请求失败: '+e.message);
      }
    }

    async function quickQuery(device, msg) {
      const el = document.getElementById('cfg-query-result') || document.getElementById('cfg-dg-tool-result');
      if(el){el.style.display='block';el.className='config-result';el.textContent='⏳ 查询中...';}
      addMsg('user', msg);
      const d = devices.find(x => x.id === selectedId);
      try {
        const r = await fetch('/api/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,context:{selected_device:d?.name||d?.remark}})});
        const res = await r.json();
        if(el){el.className=res.success?'config-result success':'config-result error';el.textContent=res.response||res.message||'';}
        addMsg('ai',(res.success?'✅ ':'❌ ')+(res.response||res.message||''));
      } catch(e) { if(el){el.className='config-result error';el.textContent='失败';} }
    }

    async function collectDeviceFacts(deviceName) {
      if(!deviceName) return;
      try {
        await fetch('/api/device/collect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({device:deviceName})});
        await loadDevices(); buildTopologyFromDevices();
        const nodes=topologyState.nodes||[]; for(const n of nodes){const dev=devices.find(x=>x.id===n.id);if(dev?.facts) n.facts=dev.facts;}
        renderTopology();
      } catch(e){console.error('采集失败:',e);}
    }

    async function refreshAllFacts() {
      if(!devices.length){addMsg('system','暂无设备');return;}
      addMsg('system','⏳ 采集中...');
      for(const d of devices){if(d.name||d.remark) await collectDeviceFacts(d.name||d.remark);}
      addMsg('system','✅ 采集完成');
    }

    // 拓扑实时刷新
    let _topoTimer = null;
    function startTopoRefresh(sec) {
      stopTopoRefresh();
      if(sec > 0) {
        _topoTimer = setInterval(async () => {
          try {
            const r = await fetch('/api/topology/discover', { method: 'POST' });
            const d = await r.json();
            if (d.success) {
              topologyState = d.state || topologyState;
              await loadDevices();
              buildTopologyFromDevices();
              await syncTopologyState();
              renderAll();
            }
          } catch(e) {}
        }, sec * 1000);
      }
    }
    function stopTopoRefresh() { if(_topoTimer){clearInterval(_topoTimer);_topoTimer=null;} }
   } catch(e) { print(e.message); }