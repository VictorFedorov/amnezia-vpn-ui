import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { serversAPI, configsAPI, vpnClientsAPI } from '../services/api';

interface SharingScore {
  config_id: number;
  sharing_score: number;
  distinct_ips_24h: number;
}

interface EndpointHistoryEntry {
  id: number;
  config_id: number;
  endpoint_ip: string;
  seen_at: string;
  created_at: string;
}

interface Server {
  id: number;
  name: string;
  host: string;
  port: number;
}

interface ServerUsersData {
  server_id: number;
  server_name: string;
  awg_peers: any[];
  wireguard_peers: any[];
  xray_clients: any[];
  xray_stats: Record<string, { uplink: number; downlink: number }>;
  awg_status: string;
  wireguard_status: string;
  xray_status: string;
}

function UsersOnServers() {
  const [servers, setServers] = useState<Server[]>([]);
  const [usersData, setUsersData] = useState<Record<number, ServerUsersData>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<Record<number, boolean>>({});
  const [expandedServers, setExpandedServers] = useState<Record<number, boolean>>({});
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState<any>(null);
  const [editFormData, setEditFormData] = useState({
    device_name: '',
    client_name: '',
    is_active: true,
  });
  const [saving, setSaving] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [savingPeer, setSavingPeer] = useState<any>(null);
  const [saveFormData, setSaveFormData] = useState({
    client_name: '',
    device_name: '',
  });
  const [clients, setClients] = useState<any[]>([]);
  const [showQRModal, setShowQRModal] = useState(false);
  const [qrConfigId, setQrConfigId] = useState<number | null>(null);
  const [qrContent, setQrContent] = useState('');
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [loadingQr, setLoadingQr] = useState(false);
  const [showBulkSaveModal, setShowBulkSaveModal] = useState(false);
  const [newUsers, setNewUsers] = useState<any[]>([]);
  const [selectedNewUsers, setSelectedNewUsers] = useState<Set<string>>(new Set());
  const [bulkSaving, setBulkSaving] = useState(false);

  // Bulk Create (new configs) modal state
  const [showBulkCreateModal, setShowBulkCreateModal] = useState(false);
  const [bulkCreateData, setBulkCreateData] = useState({
    client_id: 0,
    server_id: 0,
    protocol: 'awg',
    count: 1,
    device_name_prefix: 'Device',
  });
  const [bulkCreating, setBulkCreating] = useState(false);

  // Sharing detection
  const [sharingScores, setSharingScores] = useState<Record<number, SharingScore>>({});
  const [showEndpointHistory, setShowEndpointHistory] = useState(false);
  const [endpointHistoryConfigId, setEndpointHistoryConfigId] = useState<number | null>(null);
  const [endpointHistoryData, setEndpointHistoryData] = useState<EndpointHistoryEntry[]>([]);
  const [endpointHistoryLoading, setEndpointHistoryLoading] = useState(false);

  useEffect(() => {
    loadServersAndUsers();
    loadClients();
    loadSharingScores();
  }, []);

  const loadSharingScores = async () => {
    try {
      const alerts = await configsAPI.getSharingAlerts();
      const map: Record<number, SharingScore> = {};
      alerts.forEach((a: any) => {
        map[a.config_id] = {
          config_id: a.config_id,
          sharing_score: a.sharing_score,
          distinct_ips_24h: a.distinct_ips_24h,
        };
      });
      setSharingScores(map);
    } catch (error) {
      console.error('Failed to load sharing scores:', error);
    }
  };

  const handleShowEndpointHistory = async (configId: number) => {
    setEndpointHistoryConfigId(configId);
    setShowEndpointHistory(true);
    setEndpointHistoryLoading(true);
    try {
      const data = await configsAPI.getEndpointHistory(configId);
      setEndpointHistoryData(data);
    } catch (error) {
      console.error('Failed to load endpoint history:', error);
      setEndpointHistoryData([]);
    } finally {
      setEndpointHistoryLoading(false);
    }
  };

  const handleBulkCreate = async () => {
    if (!bulkCreateData.client_id || !bulkCreateData.server_id) {
      alert('Выберите клиента и сервер');
      return;
    }
    setBulkCreating(true);
    try {
      await configsAPI.bulkCreate(bulkCreateData);
      setShowBulkCreateModal(false);
      await loadServersAndUsers();
      alert(`Создано ${bulkCreateData.count} конфигов`);
    } catch (error) {
      console.error('Bulk create failed:', error);
      alert('Ошибка при создании конфигов');
    } finally {
      setBulkCreating(false);
    }
  };

  const loadClients = async () => {
    try {
      const data = await vpnClientsAPI.getAll();
      setClients(data);
      console.log('Loaded clients:', data); // Для отладки
    } catch (error) {
      console.error('Failed to load clients:', error);
      setClients([]); // Устанавливаем пустой массив в случае ошибки
    }
  };

  const loadServersAndUsers = async () => {
    try {
      setLoading(true);
      const serversData = await serversAPI.getAll();
      setServers(serversData);

      // Сначала загружаем данные из БД (быстро)
      for (const server of serversData) {
        await loadConfigsFromDB(server.id);
      }
      
      setLoading(false);

      // Затем автоматически обновляем трафик с серверов в фоне (без блокировки UI)
      for (const server of serversData) {
        fetchServerUsers(server.id);
      }
    } catch (error) {
      console.error('Failed to load servers:', error);
      setLoading(false);
    }
  };

  const loadConfigsFromDB = async (serverId: number) => {
    try {
      const configs = await configsAPI.getAll(serverId);
      
      // Преобразуем данные из БД в формат для отображения
      const awg_peers = configs
        .filter((c: any) => c.protocol === 'awg')
        .map((c: any) => ({
          config_id: c.id,
          client_id: c.client_id,
          client_name: c.client?.name || 'Unknown',
          device_name: c.device_name,
          public_key: c.peer_public_key,
          endpoint: c.endpoint,
          allowed_ips: c.allowed_ips,
          transfer_rx: c.bytes_received,
          transfer_tx: c.bytes_sent,
          is_active: c.is_active,
          is_online: c.is_online,
          latest_handshake: c.last_handshake,
          config_content: c.config_content,
        }));

      const wireguard_peers = configs
        .filter((c: any) => c.protocol === 'wireguard')
        .map((c: any) => ({
          config_id: c.id,
          client_id: c.client_id,
          client_name: c.client?.name || 'Unknown',
          device_name: c.device_name,
          public_key: c.peer_public_key,
          endpoint: c.endpoint,
          allowed_ips: c.allowed_ips,
          transfer_rx: c.bytes_received,
          transfer_tx: c.bytes_sent,
          is_active: c.is_active,
          is_online: c.is_online,
          latest_handshake: c.last_handshake,
          config_content: c.config_content,
        }));

      const xray_clients = configs
        .filter((c: any) => ['vless', 'vmess', 'trojan', 'shadowsocks'].includes(c.protocol))
        .map((c: any) => ({
          config_id: c.id,
          client_id: c.client_id,
          user_id: c.user_id,
          username: c.client?.name || null,
          client_name: c.client?.name || null,
          device_name: c.device_name,
          uuid: c.client_uuid,
          email: c.client_email,
          protocol: c.protocol,
          transfer_tx: c.bytes_sent,
          transfer_rx: c.bytes_received,
          is_active: c.is_active,
          is_online: c.is_online,
          config_content: c.config_content,
        }));

      const server = servers.find((s: any) => s.id === serverId);
      
      setUsersData(prev => ({
        ...prev,
        [serverId]: {
          server_id: serverId,
          server_name: server?.name || '',
          awg_peers,
          wireguard_peers,
          xray_clients,
          xray_stats: {},
          awg_status: 'cached',
          wireguard_status: 'cached',
          xray_status: 'cached',
        },
      }));
    } catch (error) {
      console.error(`Failed to load configs from DB for server ${serverId}:`, error);
    }
  };

  const fetchServerUsers = async (serverId: number) => {
    setRefreshing(prev => ({ ...prev, [serverId]: true }));
    try {
      const data = await serversAPI.fetchUsers(serverId);
      setUsersData(prev => ({ ...prev, [serverId]: data }));
    } catch (error) {
      console.error(`Failed to fetch users for server ${serverId}:`, error);
    } finally {
      setRefreshing(prev => ({ ...prev, [serverId]: false }));
    }
  };

  const handleSyncAll = async () => {
    setLoading(true);
    try {
      // Синхронизируем все серверы
      for (const server of servers) {
        await fetchServerUsers(server.id);
      }
      alert('✅ Все серверы синхронизированы успешно!');
    } catch (error) {
      console.error('Failed to sync all servers:', error);
      alert('❌ Ошибка при синхронизации серверов');
    } finally {
      setLoading(false);
    }
  };

  const handleBulkSave = async () => {
    // Собираем всех новых пользователей со всех серверов
    const allNewUsers: any[] = [];
    
    Object.values(usersData).forEach((serverData: any) => {
      // AWG пиры
      serverData.awg_peers?.forEach((peer: any) => {
        if (!peer.config_id) {
          allNewUsers.push({
            ...peer,
            server_id: serverData.server_id,
            server_name: serverData.server_name,
            protocol: 'awg',
            key: `awg-${serverData.server_id}-${peer.public_key}`,
          });
        }
      });
      
      // WireGuard пиры
      serverData.wireguard_peers?.forEach((peer: any) => {
        if (!peer.config_id) {
          allNewUsers.push({
            ...peer,
            server_id: serverData.server_id,
            server_name: serverData.server_name,
            protocol: 'wireguard',
            key: `wg-${serverData.server_id}-${peer.public_key}`,
          });
        }
      });
      
      // Xray клиенты
      serverData.xray_clients?.forEach((client: any) => {
        if (!client.config_id) {
          allNewUsers.push({
            ...client,
            server_id: serverData.server_id,
            server_name: serverData.server_name,
            protocol: client.protocol,
            key: `xray-${serverData.server_id}-${client.uuid}`,
          });
        }
      });
    });
    
    setNewUsers(allNewUsers);
    setSelectedNewUsers(new Set(allNewUsers.map(u => u.key)));
    setShowBulkSaveModal(true);
  };

  const handleBulkSaveConfirm = async () => {
    if (selectedNewUsers.size === 0) {
      alert('Выберите хотя бы одного пользователя для сохранения');
      return;
    }

    setBulkSaving(true);
    try {
      const usersToSave = newUsers.filter(u => selectedNewUsers.has(u.key));
      
      for (const user of usersToSave) {
        // Создаем нового клиента или используем существующего
        let clientId;
        const clientName = `${user.server_name} - ${user.device_name || 'Unknown'}`;
        const existingClient = clients.find(c => c.name.toLowerCase() === clientName.toLowerCase());
        
        if (existingClient) {
          clientId = existingClient.id;
        } else {
          const newClient = await vpnClientsAPI.create({
            name: clientName,
            is_active: true
          });
          clientId = newClient.id;
          await loadClients(); // Перезагружаем список клиентов с сервера
        }

        // Создаем конфигурацию
        const newConfig = {
          client_id: clientId,
          server_id: user.server_id,
          device_name: user.device_name || 'Unknown Device',
          protocol: user.protocol,
          config_content: '',
          peer_public_key: user.public_key || null,
          client_uuid: user.uuid || user.email || null,
          client_email: user.email || null,
          is_active: true,
        };

        await configsAPI.create(newConfig);
      }
      
      setShowBulkSaveModal(false);
      setNewUsers([]);
      setSelectedNewUsers(new Set());
      
      // Перезагружаем данные
      await loadServersAndUsers();
      
      alert(`✅ Успешно сохранено ${usersToSave.length} пользователей`);
    } catch (error) {
      console.error('Failed to bulk save users:', error);
      alert('❌ Ошибка при сохранении пользователей');
    } finally {
      setBulkSaving(false);
    }
  };

  const toggleServer = (serverId: number) => {
    setExpandedServers(prev => ({ ...prev, [serverId]: !prev[serverId] }));
  };


  const handleEdit = (peer: any, protocol: string) => {
    setEditingConfig({
      ...peer,
      protocol,
    });
    setEditFormData({
      device_name: peer.device_name || '',
      client_name: peer.client_name || '',
      is_active: peer.is_active !== undefined ? peer.is_active : true,
    });
    setShowEditModal(true);
  };

  const handleSaveEdit = async () => {
    if (!editingConfig || !editingConfig.config_id) {
      alert('Cannot edit: config not found in database');
      return;
    }

    setSaving(true);
    try {
      // Обновляем конфигурацию
      await configsAPI.update(editingConfig.config_id, {
        device_name: editFormData.device_name,
        is_active: editFormData.is_active,
      });

      // Обновляем имя клиента, если оно изменилось
      if (editingConfig.client_id && editFormData.client_name !== editingConfig.client_name) {
        await vpnClientsAPI.update(editingConfig.client_id, {
          name: editFormData.client_name,
        });
      }

      setShowEditModal(false);
      // Обновляем данные прямо в стейте, не делая SSH-запрос
      setUsersData(prev => {
        const newData = { ...prev };
        for (const key of Object.keys(newData)) {
          const sid = parseInt(key);
          const serverData = newData[sid];
          const listKeys = ['awg_peers', 'wireguard_peers', 'xray_clients'] as const;
          for (const listKey of listKeys) {
            const list = serverData[listKey] as any[];
            if (list.some((p: any) => p.config_id === editingConfig.config_id)) {
              newData[sid] = {
                ...serverData,
                [listKey]: list.map((p: any) =>
                  p.config_id === editingConfig.config_id
                    ? {
                        ...p,
                        device_name: editFormData.device_name,
                        client_name: editFormData.client_name,
                        username: editFormData.client_name,
                        is_active: editFormData.is_active,
                      }
                    : p
                ),
              };
            }
          }
        }
        return newData;
      });
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to update config');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClient = async () => {
    if (!editingConfig || !editingConfig.client_id) {
      alert('Client not linked or already removed');
      return;
    }

    if (!confirm('Удалить клиента и все связанные конфигурации из БД?')) return;

    try {
      setSaving(true);
      await vpnClientsAPI.delete(editingConfig.client_id);
      // refresh clients list
      await loadClients();

      // find the server id for this config and refresh
      const serverId = Object.keys(usersData).find(key => {
        const data = usersData[parseInt(key)];
        return data.awg_peers.some((p: any) => p.config_id === editingConfig.config_id) ||
               data.wireguard_peers.some((p: any) => p.config_id === editingConfig.config_id) ||
               (data.xray_clients || []).some((c: any) => c.config_id === editingConfig.config_id) ||
               Object.values(data.xray_stats || {}).some((s: any) => s.config_id === editingConfig.config_id);
      });
      if (serverId) await fetchServerUsers(parseInt(serverId));

      setShowEditModal(false);
      alert('Клиент удалён');
    } catch (error) {
      console.error('Failed to delete client:', error);
      alert('Ошибка при удалении клиента');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (configId: number, serverId: number) => {
    try {
      await configsAPI.toggleActive(configId);
      // Обновляем данные из БД после изменения
      await loadConfigsFromDB(serverId);
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to toggle config status');
    }
  };

  const handleSaveToDB = (peer: any, protocol: string, serverId: number) => {
    setSavingPeer({ ...peer, protocol, serverId });
    setSaveFormData({
      client_name: '',
      device_name: peer.device_name || 'Unknown Device',
    });
    setShowSaveModal(true);
  };

  const handleSaveConfirm = async () => {
    if (!saveFormData.client_name) {
      alert('Укажите имя клиента');
      return;
    }

    try {
      setSaving(true);
      
      let clientId;
      const existingClient = clients.find(c => c.name.toLowerCase() === saveFormData.client_name.trim().toLowerCase());
        
      if (existingClient) {
            clientId = existingClient.id;
      } else {
            // Создаем нового клиента
            const newClient = await vpnClientsAPI.create({
                name: saveFormData.client_name,
                is_active: true
            });
            clientId = newClient.id;
            await loadClients(); // Перезагружаем список клиентов с сервера
      }

      const newConfig = {
        client_id: clientId,
        server_id: savingPeer.serverId,
        device_name: saveFormData.device_name,
        protocol: savingPeer.protocol,
        config_content: '',
        peer_public_key: savingPeer.public_key || null,
        client_uuid: savingPeer.uuid || savingPeer.email || null,
        client_email: savingPeer.email || null,
        is_active: true,
        // Сохраняем живые данные из WireGuard/AWG
        endpoint: savingPeer.endpoint || null,
        allowed_ips: savingPeer.allowed_ips || null,
      };

      const savedConfig = await configsAPI.create(newConfig);
      setShowSaveModal(false);
      setSavingPeer(null);

      // Обновляем config_id у пира прямо в state, сохраняя живые данные
      const protocol = newConfig.protocol;
      const listKey = protocol === 'awg' ? 'awg_peers'
                    : protocol === 'wireguard' ? 'wireguard_peers'
                    : 'xray_clients';
      setUsersData(prev => {
        const serverData = prev[savingPeer.serverId];
        if (!serverData) return prev;
        const updatedList = (serverData[listKey as keyof typeof serverData] as any[]).map((p: any) => {
          const match = protocol === 'xray' || protocol === 'vless' || protocol === 'vmess' || protocol === 'trojan' || protocol === 'shadowsocks'
            ? p.uuid === (savingPeer.uuid || savingPeer.email)
            : p.public_key === savingPeer.public_key;
          if (match) {
            return {
              ...p,
              config_id: savedConfig.id,
              client_id: clientId,
              client_name: saveFormData.client_name,
              username: saveFormData.client_name,
              device_name: saveFormData.device_name,
              is_active: true,
            };
          }
          return p;
        });
        return {
          ...prev,
          [savingPeer.serverId]: { ...serverData, [listKey]: updatedList },
        };
      });
    } catch (error) {
      console.error('Failed to save config:', error);
      alert('Ошибка при сохранении');
    } finally {
      setSaving(false);
    }
  };

  const handleShowQR = async (configId: number, configContent: string) => {
    console.log('handleShowQR called with configId:', configId, 'configContent length:', configContent?.length);
    console.log('Current qrImage before setting modal:', qrImage);
    
    // Clean up previous blob URL
    if (qrImage && qrImage.startsWith('blob:')) {
      URL.revokeObjectURL(qrImage);
      console.log('Revoked previous blob URL:', qrImage);
    }
    
    // Prevent multiple simultaneous calls
    if (loadingQr) {
      console.log('QR loading already in progress, skipping');
      return;
    }
    
    setQrConfigId(configId);
    setQrContent(configContent);
    setShowQRModal(true);
    await loadQrCode(configId, 'amnezia');
  };

  const loadQrCode = async (configId: number, format: 'standard' | 'amnezia') => {
    setLoadingQr(true);
    setQrImage(null); // Clear previous image
    try {
      console.log('Loading QR code for config', configId, 'format:', format);
      const blob = await configsAPI.getQRCode(configId, format);
      console.log('Received blob:', blob, 'type:', blob.type, 'size:', blob.size);
      
      // Check if the blob is actually JSON (error message)
      if (blob.type === 'application/json') {
          const text = await blob.text();
          console.error('QR Code API Error:', text);
          setQrImage(null);
          return;
      }
      
      if (blob.size === 0) {
        console.error('QR Code blob is empty');
        setQrImage(null);
        return;
      }
      
      // Verify blob content is actually PNG
      const arrayBuffer = await blob.arrayBuffer();
      const uint8Array = new Uint8Array(arrayBuffer);
      const isPNG = uint8Array.length >= 8 && 
                   uint8Array[0] === 0x89 && uint8Array[1] === 0x50 && 
                   uint8Array[2] === 0x4E && uint8Array[3] === 0x47;
      console.log('Blob content check - isPNG:', isPNG, 'first 8 bytes:', Array.from(uint8Array.slice(0, 8)));
      
      if (!isPNG) {
        console.error('Blob does not contain valid PNG data');
        setQrImage(null);
        return;
      }
      
      const url = URL.createObjectURL(blob);
      console.log('Created blob URL:', url);
      setQrImage(url);
    } catch (error) {
      console.error('Failed to load QR code:', error);
      setQrImage(null); // Ensure null on error
    } finally {
      setLoadingQr(false);
    }
  };

  const closeQRModal = () => {
    // Clean up blob URL to prevent memory leaks
    if (qrImage && qrImage.startsWith('blob:')) {
      URL.revokeObjectURL(qrImage);
      console.log('Revoked blob URL on modal close:', qrImage);
    }
    setShowQRModal(false);
    setQrImage(null);
    setQrConfigId(null);
    setQrContent('');
  };

  const handleDownloadQR = () => {
    if (!qrConfigId || !qrImage) return;
    const link = document.createElement('a');
    link.href = qrImage;
    link.download = `config-${qrConfigId}-amnezia.png`;
    link.click();
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Клиенты VPN на серверах</h1>
            <div className="flex gap-3">
              <button
                onClick={handleSyncAll}
                disabled={loading}
                className="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded disabled:opacity-50 flex items-center"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {loading ? 'Синхронизация...' : '🔄 Синхронизировать БД'}
              </button>
              {(() => {
                const newUsersCount = Object.values(usersData).reduce((count, serverData: any) => {
                  const awgNew = serverData.awg_peers?.filter((p: any) => !p.config_id).length || 0;
                  const wgNew = serverData.wireguard_peers?.filter((p: any) => !p.config_id).length || 0;
                  const xrayNew = serverData.xray_clients?.filter((c: any) => !c.config_id).length || 0;
                  return count + awgNew + wgNew + xrayNew;
                }, 0);
                return newUsersCount > 0 ? (
                  <button
                    onClick={handleBulkSave}
                    className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded flex items-center"
                  >
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    💾 Сохранить новых ({newUsersCount})
                  </button>
                ) : null;
              })()}
              <button
                onClick={() => {
                  setBulkCreateData({
                    client_id: clients[0]?.id || 0,
                    server_id: servers[0]?.id || 0,
                    protocol: 'awg',
                    count: 1,
                    device_name_prefix: 'Device',
                  });
                  setShowBulkCreateModal(true);
                }}
                className="bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 px-4 rounded flex items-center"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14v6m-3-3h6M6 10h2a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v2a2 2 0 002 2zm10 0h2a2 2 0 002-2V6a2 2 0 00-2-2h-2a2 2 0 00-2 2v2a2 2 0 002 2zM6 20h2a2 2 0 002-2v-2a2 2 0 00-2-2H6a2 2 0 00-2 2v2a2 2 0 002 2z" />
                </svg>
                Bulk Create
              </button>
            </div>
          </div>

          {loading ? (
            <div className="bg-white shadow rounded-lg p-6 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600">Загрузка данных...</p>
            </div>
          ) : servers.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-6 text-center text-gray-500">
              Серверы не найдены
            </div>
          ) : (
            <div className="space-y-4">
              {servers.map((server) => {
                const data = usersData[server.id];
                const isExpanded = expandedServers[server.id];
                const isRefreshing = refreshing[server.id];

                return (
                  <div key={server.id} className="bg-white shadow rounded-lg overflow-hidden">
                    {/* Server Header */}
                    <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-b border-gray-200">
                      <div className="flex items-center space-x-4">
                        <button
                          onClick={() => toggleServer(server.id)}
                          className="text-gray-500 hover:text-gray-700"
                        >
                          <svg
                            className={`w-5 h-5 transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                        <div>
                          <h2 className="text-lg font-semibold text-gray-900">{server.name}</h2>
                          <p className="text-sm text-gray-500">{server.host}:{server.port}</p>
                        </div>
                        {data && (
                          <div className="flex gap-2">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              data.awg_status === 'ok' || data.awg_status === 'active'
                                ? 'bg-green-100 text-green-800'
                                : data.awg_status === 'cached'
                                ? 'bg-blue-100 text-blue-800'
                                : data.awg_status === 'inactive'
                                ? 'bg-gray-100 text-gray-600'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              AWG: {data.awg_status}
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              data.wireguard_status === 'ok' || data.wireguard_status === 'active'
                                ? 'bg-green-100 text-green-800'
                                : data.wireguard_status === 'cached'
                                ? 'bg-blue-100 text-blue-800'
                                : data.wireguard_status === 'inactive'
                                ? 'bg-gray-100 text-gray-600'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              WireGuard: {data.wireguard_status}
                            </span>
                            <span className={`px-2 py-1 rounded text-xs font-medium ${
                              data.xray_status === 'ok' || data.xray_status === 'active'
                                ? 'bg-green-100 text-green-800'
                                : data.xray_status === 'cached'
                                ? 'bg-blue-100 text-blue-800'
                                : data.xray_status === 'inactive'
                                ? 'bg-gray-100 text-gray-600'
                                : 'bg-red-100 text-red-800'
                            }`}>
                              XRay: {data.xray_status}
                            </span>
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() => fetchServerUsers(server.id)}
                        disabled={isRefreshing}
                        className="text-blue-600 hover:text-blue-800 disabled:opacity-50 flex items-center text-sm"
                      >
                        <svg className={`w-4 h-4 mr-1 ${isRefreshing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Обновить
                      </button>
                    </div>

                    {/* Server Content */}
                    {isExpanded && data && (
                      <div className="p-6">
                        {/* AWG Section */}
                        <div className="mb-6">
                          <div className="flex items-center mb-3">
                            <span className="px-3 py-1 bg-purple-100 text-purple-800 rounded-md text-sm font-semibold">
                              AmneziaWG
                            </span>
                            {data.awg_peers && data.awg_peers.length > 0 && (
                              <span className="ml-2 text-sm text-gray-600">
                                {data.awg_peers.length} peer(s)
                              </span>
                            )}
                          </div>
                          {data.awg_peers && data.awg_peers.length > 0 ? (
                            <div className="bg-gray-50 rounded-lg overflow-hidden">
                              <table className="min-w-full">
                                <thead className="bg-gray-100">
                                  <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Client / Device</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Public Key</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Endpoint</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Allowed IPs</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Transfer (RX/TX)</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Actions</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 bg-white">
                                  {data.awg_peers.map((peer: any, idx: number) => (
                                    <tr key={idx} className="hover:bg-gray-50">
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        <div className="flex flex-col">
                                          <span className="font-semibold">{peer.client_name || 'Unknown'}</span>
                                          <span className="text-gray-500">{peer.device_name}</span>
                                        </div>
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600 font-mono">
                                        {peer.public_key?.substring(0, 20)}...
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        {peer.endpoint || <span className="text-gray-400">N/A</span>}
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        {peer.allowed_ips || <span className="text-gray-400">N/A</span>}
                                      </td>
                                      <td className="px-4 py-3 text-xs">
                                        {peer.is_active !== null ? (
                                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                                            peer.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                          }`}>
                                            {peer.is_active ? 'Active' : 'Inactive'}
                                          </span>
                                        ) : (
                                          <span className="text-gray-400">N/A</span>
                                        )}
                                        {peer.is_online && (
                                          <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                                            Online
                                          </span>
                                        )}
                                        {peer.config_id && sharingScores[peer.config_id] && sharingScores[peer.config_id].sharing_score > 0 && (
                                          <span
                                            className={`ml-2 px-2 py-1 rounded text-xs font-medium cursor-pointer hover:opacity-80 ${
                                              sharingScores[peer.config_id].sharing_score >= 2
                                                ? 'bg-red-100 text-red-800'
                                                : 'bg-orange-100 text-orange-800'
                                            }`}
                                            title={`${sharingScores[peer.config_id].distinct_ips_24h} IPs за 24ч — нажмите для деталей`}
                                            onClick={() => handleShowEndpointHistory(peer.config_id)}
                                          >
                                            {sharingScores[peer.config_id].distinct_ips_24h} IP — {sharingScores[peer.config_id].sharing_score >= 2 ? 'Shared!' : 'Shared?'}
                                          </span>
                                        )}
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        <div className="flex flex-col">
                                          <span>↓ {(peer.transfer_rx / 1024 / 1024).toFixed(2)} MB</span>
                                          <span>↑ {(peer.transfer_tx / 1024 / 1024).toFixed(2)} MB</span>
                                        </div>
                                      </td>
                                      <td className="px-4 py-3 text-right">
                                        {peer.config_id ? (
                                          <div className="flex items-center justify-end gap-2">
                                            <button
                                              onClick={() => handleToggleActive(peer.config_id, server.id)}
                                              className={`px-2 py-1 rounded text-xs font-medium ${
                                                peer.is_active 
                                                  ? 'bg-red-100 text-red-700 hover:bg-red-200' 
                                                  : 'bg-green-100 text-green-700 hover:bg-green-200'
                                              }`}
                                              title={peer.is_active ? 'Block access' : 'Unblock access'}
                                            >
                                              {peer.is_active ? 'Block' : 'Unblock'}
                                            </button>
                                            <button
                                              onClick={() => handleEdit(peer, 'awg')}
                                              className="text-blue-600 hover:text-blue-800 text-xs"
                                            >
                                              Edit
                                            </button>
                                            <button
                                              onClick={() => handleShowQR(peer.config_id, peer.config_content || '')}
                                              className="text-green-600 hover:text-green-800 text-xs"
                                              title="Показать QR код"
                                            >
                                              QR
                                            </button>
                                          </div>
                                        ) : (
                                          <button
                                            onClick={() => handleSaveToDB(peer, 'awg', server.id)}
                                            className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 hover:bg-blue-200"
                                          >
                                            Сохранить в БД
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-sm text-gray-500 bg-gray-50 rounded p-4">No AWG peers found</p>
                          )}
                        </div>

                        {/* WireGuard Section */}
                        <div className="mb-6">
                          <div className="flex items-center mb-3">
                            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-md text-sm font-semibold">
                              WireGuard
                            </span>
                            {data.wireguard_peers && data.wireguard_peers.length > 0 && (
                              <span className="ml-2 text-sm text-gray-600">
                                {data.wireguard_peers.length} peer(s)
                              </span>
                            )}
                          </div>
                          {data.wireguard_peers && data.wireguard_peers.length > 0 ? (
                            <div className="bg-gray-50 rounded-lg overflow-hidden">
                              <table className="min-w-full">
                                <thead className="bg-gray-100">
                                  <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Client / Device</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Public Key</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Endpoint</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Allowed IPs</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Transfer (RX/TX)</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Actions</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 bg-white">
                                  {data.wireguard_peers.map((peer: any, idx: number) => (
                                    <tr key={idx} className="hover:bg-gray-50">
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        <div className="flex flex-col">
                                          <span className="font-semibold">{peer.client_name || 'Unknown'}</span>
                                          <span className="text-gray-500">{peer.device_name}</span>
                                        </div>
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600 font-mono">
                                        {peer.public_key?.substring(0, 20)}...
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        {peer.endpoint || <span className="text-gray-400">N/A</span>}
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        {peer.allowed_ips || <span className="text-gray-400">N/A</span>}
                                      </td>
                                      <td className="px-4 py-3 text-xs">
                                        {peer.is_active !== null ? (
                                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                                            peer.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                          }`}>
                                            {peer.is_active ? 'Active' : 'Inactive'}
                                          </span>
                                        ) : (
                                          <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-medium">
                                            Not in DB
                                          </span>
                                        )}
                                        {peer.config_id && sharingScores[peer.config_id] && sharingScores[peer.config_id].sharing_score > 0 && (
                                          <span
                                            className={`ml-2 px-2 py-1 rounded text-xs font-medium cursor-pointer hover:opacity-80 ${
                                              sharingScores[peer.config_id].sharing_score >= 2
                                                ? 'bg-red-100 text-red-800'
                                                : 'bg-orange-100 text-orange-800'
                                            }`}
                                            title={`${sharingScores[peer.config_id].distinct_ips_24h} IPs за 24ч — нажмите для деталей`}
                                            onClick={() => handleShowEndpointHistory(peer.config_id)}
                                          >
                                            {sharingScores[peer.config_id].distinct_ips_24h} IP — {sharingScores[peer.config_id].sharing_score >= 2 ? 'Shared!' : 'Shared?'}
                                          </span>
                                        )}
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        ↓ {peer.transfer_rx ? (peer.transfer_rx / 1024 / 1024).toFixed(2) : 0} MB<br />
                                        ↑ {peer.transfer_tx ? (peer.transfer_tx / 1024 / 1024).toFixed(2) : 0} MB
                                      </td>
                                      <td className="px-4 py-3 text-right">
                                        {peer.config_id ? (
                                          <div className="flex items-center justify-end gap-2">
                                            <button
                                              onClick={() => handleToggleActive(peer.config_id, server.id)}
                                              className={`px-2 py-1 rounded text-xs font-medium ${
                                                peer.is_active
                                                  ? 'bg-red-100 text-red-700 hover:bg-red-200'
                                                  : 'bg-green-100 text-green-700 hover:bg-green-200'
                                              }`}
                                              title={peer.is_active ? 'Block access' : 'Unblock access'}
                                            >
                                              {peer.is_active ? 'Block' : 'Unblock'}
                                            </button>
                                            <button
                                              onClick={() => handleEdit(peer, 'wireguard')}
                                              className="text-blue-600 hover:text-blue-800 text-xs"
                                            >
                                              Edit
                                            </button>
                                            <button
                                              onClick={() => handleShowQR(peer.config_id, peer.config_content || '')}
                                              className="text-green-600 hover:text-green-800 text-xs"
                                              title="Показать QR код"
                                            >
                                              QR
                                            </button>
                                          </div>
                                        ) : (
                                          <button
                                            onClick={() => handleSaveToDB(peer, 'wireguard', server.id)}
                                            className="px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 hover:bg-blue-200"
                                          >
                                            Сохранить в БД
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="text-sm text-gray-500 bg-gray-50 rounded p-4">No WireGuard peers found</p>
                          )}
                        </div>

                        {/* XRay Section */}
                        <div>
                          <div className="flex items-center mb-3">
                            <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-md text-sm font-semibold">
                              XRay
                            </span>
                            {data.xray_clients && data.xray_clients.length > 0 && (
                              <span className="ml-2 text-sm text-gray-600">
                                {data.xray_clients.length} user(s)
                              </span>
                            )}
                          </div>
                          {data.xray_clients && data.xray_clients.length > 0 ? (
                            <div className="bg-gray-50 rounded-lg overflow-hidden">
                              <table className="min-w-full">
                                <thead className="bg-gray-100">
                                  <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Client / Device</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">UUID</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Protocol</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Flow</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Uplink</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Downlink</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Total</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">Actions</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 bg-white">
                                  {data.xray_clients.map((client: any) => (
                                    <tr key={client.uuid} className="hover:bg-gray-50">
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        <div className="flex flex-col">
                                          <span className="font-semibold">{client.client_name || client.username || 'Unknown'}</span>
                                          <span className="text-gray-500">{client.device_name}</span>
                                        </div>
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600 font-mono">
                                        {client.uuid.substring(0, 24)}...
                                      </td>
                                      <td className="px-4 py-3 text-xs">
                                        <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs font-medium uppercase">
                                          {client.protocol}
                                        </span>
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        {client.flow || 'N/A'}
                                      </td>
                                      <td className="px-4 py-3 text-xs">
                                        {client.config_id ? (
                                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                                            client.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                          }`}>
                                            {client.is_active ? 'Active' : 'Inactive'}
                                          </span>
                                        ) : (
                                          <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-medium">
                                            Not in DB
                                          </span>
                                        )}
                                        {client.config_id && sharingScores[client.config_id] && sharingScores[client.config_id].sharing_score > 0 && (
                                          <span
                                            className={`ml-2 px-2 py-1 rounded text-xs font-medium cursor-pointer hover:opacity-80 ${
                                              sharingScores[client.config_id].sharing_score >= 2
                                                ? 'bg-red-100 text-red-800'
                                                : 'bg-orange-100 text-orange-800'
                                            }`}
                                            title={`${sharingScores[client.config_id].distinct_ips_24h} IPs за 24ч — нажмите для деталей`}
                                            onClick={() => handleShowEndpointHistory(client.config_id)}
                                          >
                                            {sharingScores[client.config_id].distinct_ips_24h} IP — {sharingScores[client.config_id].sharing_score >= 2 ? 'Shared!' : 'Shared?'}
                                          </span>
                                        )}
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        ↑ {(client.transfer_tx / 1024 / 1024).toFixed(2)} MB
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600">
                                        ↓ {(client.transfer_rx / 1024 / 1024).toFixed(2)} MB
                                      </td>
                                      <td className="px-4 py-3 text-xs text-gray-600 font-semibold">
                                        {((client.transfer_tx + client.transfer_rx) / 1024 / 1024).toFixed(2)} MB
                                      </td>
                                      <td className="px-4 py-3 text-right">
                                        {client.config_id ? (
                                          <div className="flex items-center justify-end gap-2">
                                            <button
                                              onClick={() => handleToggleActive(client.config_id, server.id)}
                                              className={`px-2 py-1 rounded text-xs font-medium ${
                                                client.is_active 
                                                  ? 'bg-red-100 text-red-700 hover:bg-red-200' 
                                                  : 'bg-green-100 text-green-700 hover:bg-green-200'
                                              }`}
                                              title={client.is_active ? 'Block access' : 'Unblock access'}
                                            >
                                              {client.is_active ? 'Block' : 'Unblock'}
                                            </button>
                                            <button
                                              onClick={() => handleEdit(client, client.protocol)}
                                              className="text-blue-600 hover:text-blue-800 text-xs"
                                            >
                                              Edit
                                            </button>
                                            <button
                                              onClick={() => handleShowQR(client.config_id, '')}
                                              className="text-green-600 hover:text-green-800 text-xs"
                                              title="Показать QR код"
                                            >
                                              QR
                                            </button>
                                          </div>
                                        ) : (
                                          <button
                                            onClick={() => handleSaveToDB(client, client.protocol, server.id)}
                                            className="px-2 py-1 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded text-xs font-medium"
                                            title="Сохранить в базу данных"
                                          >
                                            Save to DB
                                          </button>
                                        )}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <div className="text-center py-8 text-gray-500">
                              <p>No XRay clients found</p>
                              <button
                                onClick={() => fetchServerUsers(server.id)}
                                className="mt-2 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
                              >
                                Refresh from server
                              </button>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      {showEditModal && editingConfig && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowEditModal(false)}></div>
            <div className="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all max-w-lg w-full z-20">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Редактировать конфигурацию устройства
                </h3>

                <div className="space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="text-sm">
                      <p className="font-medium text-blue-800">Protocol: {editingConfig.protocol?.toUpperCase()}</p>
                      <p className="text-blue-600 font-mono text-xs mt-1">
                        {editingConfig.public_key?.substring(0, 30) || editingConfig.client_uuid?.substring(0, 30) || 'N/A'}...
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Название устройства
                    </label>
                    <input
                      type="text"
                      value={editFormData.device_name}
                      onChange={(e) => setEditFormData({ ...editFormData, device_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="iPhone 13, MacBook Pro, etc."
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Имя клиента
                    </label>
                    <input
                      type="text"
                      value={editFormData.client_name}
                      onChange={(e) => setEditFormData({ ...editFormData, client_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Иван Иванов, Корпоративный VPN, etc."
                    />
                  </div>

                  <div>
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editFormData.is_active}
                        onChange={(e) => setEditFormData({ ...editFormData, is_active: e.target.checked })}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-sm font-medium text-gray-700">Устройство активно</span>
                    </label>
                    <p className="text-xs text-gray-500 mt-1 ml-6">
                      Неактивные устройства не смогут подключаться
                    </p>
                  </div>

                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-600 space-y-1">
                      <p><span className="font-medium">Клиент:</span> {editFormData.client_name || 'Неизвестен'}</p>
                      <p><span className="font-medium">ID конфигурации:</span> {editingConfig.config_id}</p>
                      {editingConfig.endpoint && (
                        <p><span className="font-medium">Текущий статус:</span> <span className="text-green-600">Онлайн</span></p>
                      )}
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end space-x-3">
                  {editingConfig.client_id && (
                    <button
                      onClick={handleDeleteClient}
                      disabled={saving}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                    >
                      {saving ? 'Удаление...' : 'Удалить клиента'}
                    </button>
                  )}
                  <button
                    onClick={() => setShowEditModal(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                    disabled={saving}
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleSaveEdit}
                    disabled={saving}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {saving ? 'Сохранение...' : 'Сохранить изменения'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Save to DB Modal */}
      {showSaveModal && savingPeer && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowSaveModal(false)}></div>
            <div className="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all max-w-lg w-full z-20">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Сохранить в базу данных
                </h3>

                <div className="space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="text-sm">
                      <p className="font-medium text-blue-800">Protocol: {savingPeer.protocol?.toUpperCase()}</p>
                      <p className="text-blue-600 font-mono text-xs mt-1">
                        {savingPeer.public_key?.substring(0, 30) || savingPeer.email?.substring(0, 30) || 'N/A'}...
                      </p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Клиент * (введите имя)
                    </label>
                    <input
                      type="text"
                      list="clients-list"
                      value={saveFormData.client_name}
                      onChange={(e) => setSaveFormData({ ...saveFormData, client_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Введите имя клиента"
                    />
                    <datalist id="clients-list">
                      {Array.isArray(clients) && clients.map((client) => (
                        <option key={client.id} value={client.name} />
                      ))}
                    </datalist>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Название устройства
                    </label>
                    <input
                      type="text"
                      value={saveFormData.device_name}
                      onChange={(e) => setSaveFormData({ ...saveFormData, device_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="iPhone 13, MacBook Pro, etc."
                    />
                  </div>
                </div>

                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={() => setShowSaveModal(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                    disabled={saving}
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleSaveConfirm}
                    disabled={saving}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {saving ? 'Сохранение...' : 'Сохранить'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* QR Code Modal */}
      {showQRModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={closeQRModal}></div>
            <div className="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all max-w-lg w-full z-20">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4 text-center">
                  QR Код конфигурации
                </h3>

                <div className="flex flex-col items-center space-y-4">
                  {qrConfigId && (
                    <div className="bg-white p-4 rounded-lg border-2 border-gray-200 min-h-[256px] flex items-center justify-center">
                      {console.log('Rendering QR modal - loadingQr:', loadingQr, 'qrImage:', qrImage)}
                      {loadingQr ? (
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                      ) : qrImage ? (
                        <div>
                          {console.log('Rendering QR image with src:', qrImage)}
                          <img 
                            src={qrImage}
                            alt="QR Code"
                            className="w-64 h-64"
                            onLoad={() => console.log('QR image loaded successfully')}
                            onError={(e) => console.error('QR image failed to load:', e)}
                          />
                        </div>
                      ) : (
                         <div className="text-center text-gray-500 p-8">
                            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <p className="mt-2 text-sm font-medium text-gray-900">QR код недоступен</p>
                            <p className="mt-1 text-xs text-gray-500 max-w-xs">
                                Невозможно сгенерировать QR код для импортированной конфигурации (отсутствует приватный ключ).
                            </p>
                         </div>
                      )}
                    </div>
                  )}

                  {qrContent && (
                    <div className="w-full">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Текст конфигурации:
                      </label>
                      <textarea
                        value={qrContent}
                        readOnly
                        className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 font-mono text-xs h-32"
                      />
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(qrContent);
                          alert('Скопировано!');
                        }}
                        className="mt-2 w-full px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                      >
                        Копировать конфигурацию
                      </button>
                    </div>
                  )}
                </div>

                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={closeQRModal}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                  >
                    Закрыть
                  </button>
                  <button
                    onClick={handleDownloadQR}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Скачать QR
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Save Modal */}
      {showBulkSaveModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowBulkSaveModal(false)}></div>
            <div className="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all max-w-6xl w-full z-20">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-medium text-gray-900">
                    Сохранить новых пользователей ({newUsers.length})
                  </h3>
                  <button
                    onClick={() => setShowBulkSaveModal(false)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="mb-4 flex items-center space-x-4">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedNewUsers.size === newUsers.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedNewUsers(new Set(newUsers.map(u => u.key)));
                        } else {
                          setSelectedNewUsers(new Set());
                        }
                      }}
                      className="mr-2"
                    />
                    Выбрать всех
                  </label>
                  <span className="text-sm text-gray-600">
                    Выбрано: {selectedNewUsers.size} из {newUsers.length}
                  </span>
                </div>

                <div className="max-h-96 overflow-y-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Выбрать</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Сервер</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Протокол</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Устройство</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Идентификатор</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Статус</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {newUsers.map((user) => (
                        <tr key={user.key} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <input
                              type="checkbox"
                              checked={selectedNewUsers.has(user.key)}
                              onChange={(e) => {
                                const newSelected = new Set(selectedNewUsers);
                                if (e.target.checked) {
                                  newSelected.add(user.key);
                                } else {
                                  newSelected.delete(user.key);
                                }
                                setSelectedNewUsers(newSelected);
                              }}
                            />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{user.server_name}</td>
                          <td className="px-4 py-3 text-sm">
                            <span className={`px-2 py-1 rounded text-xs font-medium uppercase ${
                              user.protocol === "awg" ? "bg-purple-100 text-purple-800" :
                              user.protocol === "wireguard" ? "bg-blue-100 text-blue-800" :
                              "bg-green-100 text-green-800"
                            }`}>
                              {user.protocol}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{user.device_name || "Unknown"}</td>
                          <td className="px-4 py-3 text-sm text-gray-600 font-mono">
                            {user.public_key ? user.public_key.substring(0, 24) + "..." :
                             user.uuid ? user.uuid.substring(0, 24) + "..." : "N/A"}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-medium">
                              New
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={() => setShowBulkSaveModal(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                    disabled={bulkSaving}
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleBulkSaveConfirm}
                    disabled={bulkSaving || selectedNewUsers.size === 0}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                  >
                    {bulkSaving ? "Сохранение..." : `Сохранить выбранных (${selectedNewUsers.size})`}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Endpoint History Modal */}
      {showEndpointHistory && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowEndpointHistory(false)}></div>
            <div className="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all max-w-2xl w-full z-20">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-medium text-gray-900">
                    История подключений (Config #{endpointHistoryConfigId})
                  </h3>
                  <button onClick={() => setShowEndpointHistory(false)} className="text-gray-400 hover:text-gray-600">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {endpointHistoryLoading ? (
                  <div className="text-center py-8">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  </div>
                ) : endpointHistoryData.length === 0 ? (
                  <p className="text-center text-gray-500 py-8">Нет записей</p>
                ) : (
                  <>
                    <p className="text-sm text-gray-500 mb-3">
                      Уникальных IP: {new Set(endpointHistoryData.map(e => e.endpoint_ip)).size} | Последние {endpointHistoryData.length} записей
                    </p>
                    <div className="max-h-96 overflow-y-auto">
                      <table className="min-w-full divide-y divide-gray-200 text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                          <tr>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">IP-адрес</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Время</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {endpointHistoryData.map((entry) => (
                            <tr key={entry.id} className="hover:bg-gray-50">
                              <td className="px-4 py-2 font-mono text-gray-900">{entry.endpoint_ip}</td>
                              <td className="px-4 py-2 text-gray-600">{new Date(entry.seen_at).toLocaleString('ru-RU')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}

                <div className="mt-4 flex justify-end">
                  <button
                    onClick={() => setShowEndpointHistory(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                  >
                    Закрыть
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Create Modal */}
      {showBulkCreateModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowBulkCreateModal(false)}></div>
            <div className="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all max-w-lg w-full z-20">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Bulk Create Configs</h3>
                  <button onClick={() => setShowBulkCreateModal(false)} className="text-gray-400 hover:text-gray-600">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Клиент</label>
                    <select
                      value={bulkCreateData.client_id}
                      onChange={(e) => setBulkCreateData({ ...bulkCreateData, client_id: Number(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    >
                      <option value={0}>-- Выберите клиента --</option>
                      {clients.map((c: any) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Сервер</label>
                    <select
                      value={bulkCreateData.server_id}
                      onChange={(e) => setBulkCreateData({ ...bulkCreateData, server_id: Number(e.target.value) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    >
                      <option value={0}>-- Выберите сервер --</option>
                      {servers.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Протокол</label>
                    <select
                      value={bulkCreateData.protocol}
                      onChange={(e) => setBulkCreateData({ ...bulkCreateData, protocol: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    >
                      <option value="awg">AWG</option>
                      <option value="wireguard">WireGuard</option>
                      <option value="vless">VLESS</option>
                      <option value="vmess">VMess</option>
                      <option value="trojan">Trojan</option>
                      <option value="shadowsocks">Shadowsocks</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Количество (1-50)</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={bulkCreateData.count}
                      onChange={(e) => setBulkCreateData({ ...bulkCreateData, count: Math.min(50, Math.max(1, Number(e.target.value))) })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Префикс имени</label>
                    <input
                      type="text"
                      value={bulkCreateData.device_name_prefix}
                      onChange={(e) => setBulkCreateData({ ...bulkCreateData, device_name_prefix: e.target.value })}
                      placeholder="Device"
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      Результат: {bulkCreateData.device_name_prefix} 1, {bulkCreateData.device_name_prefix} 2, ...
                    </p>
                  </div>
                </div>

                <div className="mt-6 flex justify-end space-x-3">
                  <button
                    onClick={() => setShowBulkCreateModal(false)}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                    disabled={bulkCreating}
                  >
                    Отмена
                  </button>
                  <button
                    onClick={handleBulkCreate}
                    disabled={bulkCreating || !bulkCreateData.client_id || !bulkCreateData.server_id}
                    className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
                  >
                    {bulkCreating ? 'Создание...' : `Создать ${bulkCreateData.count} конфигов`}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

    </Layout>
  );
}

export default UsersOnServers;
