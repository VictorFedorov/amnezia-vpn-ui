import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import Layout from '../components/Layout';
import { serversAPI, configsAPI } from '../services/api';
import { useRealtimeStore } from '../stores/realtimeStore';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

interface SharingAlertIp {
  ip: string;
  first_seen: string;
  last_seen: string;
  times_seen: number;
}

interface SharingAlert {
  config_id: number;
  device_name: string;
  client_name: string | null;
  protocol: string | null;
  is_online: boolean;
  is_active: boolean;
  distinct_ips_24h: number;
  sharing_score: number;
  ips: SharingAlertIp[];
}

function Dashboard() {
  const [stats, setStats] = useState({
    totalClients: 0,
    activeServers: 0,
    totalConfigs: 0,
    onlineDevices: 0,
    totalTraffic: '0 GB',
  });
  const [protocolStats, setProtocolStats] = useState<any[]>([]);
  const [topUsers, setTopUsers] = useState<any[]>([]);
  const [sharingAlerts, setSharingAlerts] = useState<SharingAlert[]>([]);
  const [expandedAlerts, setExpandedAlerts] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  // WebSocket realtime updates
  const { lastUpdate, connected, connect, disconnect } = useRealtimeStore();
  const lastUpdateRef = useRef(lastUpdate);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, []);

  // Reload data when WS sends traffic_update
  useEffect(() => {
    if (lastUpdate > 0 && lastUpdate !== lastUpdateRef.current) {
      lastUpdateRef.current = lastUpdate;
      loadStats();
    }
  }, [lastUpdate]);

  useEffect(() => {
    loadStats();
    loadSharingAlerts();
    const interval = setInterval(loadStats, 120000); // Fallback polling every 120s
    return () => clearInterval(interval);
  }, []);

  const loadSharingAlerts = async () => {
    try {
      const data = await configsAPI.getSharingAlerts();
      setSharingAlerts(data);
    } catch (error) {
      console.error('Failed to load sharing alerts:', error);
    }
  };

  const loadStats = async () => {
    try {
      const [servers, allConfigs] = await Promise.all([
        serversAPI.getAll(),
        configsAPI.getAll(),
      ]);

      const uniqueClients = new Set(allConfigs.map((c: any) => c.client_id).filter(Boolean));

      const onlineCount = allConfigs.filter((c: any) => c.is_online).length;
      const totalBytes = allConfigs.reduce((sum: number, c: any) =>
        sum + (c.bytes_received || 0) + (c.bytes_sent || 0), 0);
      const totalGB = (totalBytes / 1024 / 1024 / 1024).toFixed(2);

      const protocolCounts: any = {};
      allConfigs.forEach((c: any) => {
        const proto = c.protocol || 'unknown';
        protocolCounts[proto] = (protocolCounts[proto] || 0) + 1;
      });

      const protocolData = Object.entries(protocolCounts).map(([name, value]) => ({
        name: name.toUpperCase(),
        value: value,
      }));

      const clientTraffic: any = {};
      allConfigs.forEach((c: any) => {
        if (c.client_id) {
          const clientId = c.client_id;
          const clientName = c.client?.name || `Client ${clientId}`;
          const traffic = (c.bytes_received || 0) + (c.bytes_sent || 0);

          if (!clientTraffic[clientId]) {
            clientTraffic[clientId] = { username: clientName, traffic: 0 };
          }
          clientTraffic[clientId].traffic += traffic;
        }
      });

      const topUsersData = Object.values(clientTraffic)
        .sort((a: any, b: any) => b.traffic - a.traffic)
        .slice(0, 5)
        .map((u: any) => ({
          username: (u as any).username,
          traffic: ((u as any).traffic / 1024 / 1024 / 1024).toFixed(2),
        }));

      setStats({
        totalClients: uniqueClients.size,
        activeServers: servers.length,
        totalConfigs: allConfigs.length,
        onlineDevices: onlineCount,
        totalTraffic: `${totalGB} GB`,
      });
      setProtocolStats(protocolData);
      setTopUsers(topUsersData);

    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
              {connected && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <span className="w-2 h-2 rounded-full bg-green-500 mr-1 animate-pulse"></span>
                  Live
                </span>
              )}
            </div>
            <button
              onClick={loadStats}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded disabled:opacity-50"
            >
              {loading ? 'Загрузка...' : 'Обновить'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            {/* Statistics Cards */}
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-8 w-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Клиентов VPN</dt>
                      <dd className="text-2xl font-bold text-gray-900">{stats.totalClients}</dd>
                      <dd className="text-xs text-gray-500">уникальных пользователей</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Серверов</dt>
                      <dd className="text-2xl font-bold text-gray-900">{stats.activeServers}</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-8 w-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Устройств</dt>
                      <dd className="text-2xl font-bold text-gray-900">
                        {stats.onlineDevices}/{stats.totalConfigs}
                      </dd>
                      <dd className="text-xs text-gray-500">онлайн / всего (из БД)</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <svg className="h-8 w-8 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">Трафик</dt>
                      <dd className="text-2xl font-bold text-gray-900">{stats.totalTraffic}</dd>
                      <dd className="text-xs text-gray-500">кэш из БД</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sharing Alerts Card */}
          {sharingAlerts.length > 0 && (
            <div className="bg-red-50 border border-red-200 shadow rounded-lg p-6 mb-8">
              <h2 className="text-lg font-semibold text-red-800 mb-3">
                Подозрение на шаринг ({sharingAlerts.length})
              </h2>
              <p className="text-sm text-red-600 mb-4">
                Конфиги с 2+ уникальными IP за последние 24ч. Нажмите для просмотра деталей.
              </p>
              <div className="space-y-2">
                {sharingAlerts.map((alert) => {
                  const isExpanded = expandedAlerts.has(alert.config_id);
                  return (
                    <div key={alert.config_id} className="bg-white rounded border border-red-100 overflow-hidden">
                      <div
                        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50"
                        onClick={() => {
                          setExpandedAlerts(prev => {
                            const next = new Set(prev);
                            if (next.has(alert.config_id)) next.delete(alert.config_id);
                            else next.add(alert.config_id);
                            return next;
                          });
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                          <div>
                            <span className="font-medium text-gray-900">{alert.device_name}</span>
                            {alert.client_name && (
                              <span className="text-gray-500 ml-2">({alert.client_name})</span>
                            )}
                          </div>
                          {alert.protocol && (
                            <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs font-medium uppercase">
                              {alert.protocol}
                            </span>
                          )}
                          {alert.is_online && (
                            <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                              Online
                            </span>
                          )}
                          {!alert.is_active && (
                            <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-xs font-medium">
                              Blocked
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-gray-600">
                            {alert.distinct_ips_24h} IP
                          </span>
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            alert.sharing_score >= 2
                              ? 'bg-red-100 text-red-800'
                              : 'bg-orange-100 text-orange-800'
                          }`}>
                            {alert.sharing_score >= 2 ? 'Shared!' : 'Suspicious'}
                          </span>
                        </div>
                      </div>

                      {isExpanded && alert.ips && alert.ips.length > 0 && (
                        <div className="border-t border-red-100 px-4 py-3 bg-gray-50">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="text-left text-xs text-gray-500">
                                <th className="pb-2 font-medium">IP-адрес</th>
                                <th className="pb-2 font-medium">Первое появление</th>
                                <th className="pb-2 font-medium">Последнее появление</th>
                                <th className="pb-2 font-medium text-right">Раз замечен</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                              {alert.ips.map((ipDetail) => (
                                <tr key={ipDetail.ip} className="text-gray-700">
                                  <td className="py-1.5 font-mono">{ipDetail.ip}</td>
                                  <td className="py-1.5">{new Date(ipDetail.first_seen).toLocaleString('ru-RU')}</td>
                                  <td className="py-1.5">{new Date(ipDetail.last_seen).toLocaleString('ru-RU')}</td>
                                  <td className="py-1.5 text-right">{ipDetail.times_seen}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Графики */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Распределение по протоколам */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Распределение по протоколам</h2>
              {protocolStats.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={protocolStats}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, value }) => `${name}: ${value}`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {protocolStats.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-center text-gray-500 py-12">Нет данных</p>
              )}
            </div>

            {/* Топ пользователей */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Топ 5 по трафику</h2>
              {topUsers.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={topUsers}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="username" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="traffic" fill="#3B82F6" name="Трафик (GB)" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-center text-gray-500 py-12">Нет данных</p>
              )}
            </div>
          </div>

          <div className="mt-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Быстрые действия</h2>
            <div className="bg-white shadow rounded-lg p-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Link
                  to="/users-on-servers"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded text-center transition"
                >
                  Добавить клиента VPN
                </Link>
                <Link
                  to="/servers"
                  className="bg-green-600 hover:bg-green-700 text-white font-medium py-3 px-4 rounded text-center transition"
                >
                  Добавить сервер
                </Link>
                <Link
                  to="/users-on-servers"
                  className="bg-purple-600 hover:bg-purple-700 text-white font-medium py-3 px-4 rounded text-center transition"
                >
                  Клиенты на серверах
                </Link>
                <Link
                  to="/users"
                  className="bg-gray-600 hover:bg-gray-700 text-white font-medium py-3 px-4 rounded text-center transition"
                >
                  Администраторы
                </Link>
              </div>
            </div>
          </div>

          {/* Информация об обновлении */}
          <div className="mt-6 bg-blue-50 border-l-4 border-blue-400 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-blue-700">
                  <strong>Обновление данных:</strong> Статистика устройств и трафика берётся из базы данных.
                  {connected
                    ? ' Данные обновляются в реальном времени через WebSocket.'
                    : ' Чтобы обновить данные с серверов, перейдите на страницу '}
                  {!connected && <Link to="/users-on-servers" className="underline font-semibold">"Клиенты на серверах"</Link>}
                  {!connected && ' и нажмите кнопку '}
                  {!connected && <strong>"Синхронизировать БД"</strong>}
                  {!connected && '.'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default Dashboard;
