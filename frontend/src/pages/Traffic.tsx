import { useEffect, useState, useRef } from 'react';
import Layout from '../components/Layout';
import { trafficAPI } from '../services/api';
import { useRealtimeStore } from '../stores/realtimeStore';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

function Traffic() {
  const [realtime, setRealtime] = useState<any>(null);
  const [topUsers, setTopUsers] = useState<any[]>([]);
  const [byServer, setByServer] = useState<any[]>([]);
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
      loadData();
    }
  }, [lastUpdate]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 120000); // Fallback polling every 120s
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [rtData, usersData, serverData] = await Promise.all([
        trafficAPI.getRealtime(),
        trafficAPI.getTopUsers(10),
        trafficAPI.getByServer()
      ]);

      setRealtime(rtData);

      // Format data for charts
      setTopUsers(usersData.map((u: any) => ({
        name: u.username,
        traffic: parseFloat((u.total_traffic / 1024 / 1024 / 1024).toFixed(2)) // GB
      })));

      setByServer(serverData.map((s: any) => ({
        name: s.server_name,
        traffic: parseFloat((s.total_traffic / 1024 / 1024 / 1024).toFixed(2)) // GB
      })));

    } catch (error) {
      console.error('Failed to load traffic data:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (loading && !realtime) {
    return (
      <Layout>
        <div className="flex h-screen items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      </Layout>
    );
  }

  const pieData = realtime ? [
    { name: 'Download', value: realtime.total_download },
    { name: 'Upload', value: realtime.total_upload },
  ] : [];

  return (
    <Layout>
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex items-center gap-3 mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Мониторинг трафика</h1>
            {connected && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                <span className="w-2 h-2 rounded-full bg-green-500 mr-1 animate-pulse"></span>
                Live
              </span>
            )}
          </div>

          {/* Cards Row */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-gray-500 truncate">Общий трафик</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">{formatBytes(realtime?.total || 0)}</dd>
              </div>
            </div>
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-green-500 truncate">Загружено (Download)</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">{formatBytes(realtime?.total_download || 0)}</dd>
              </div>
            </div>
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <dt className="text-sm font-medium text-blue-500 truncate">Отдано (Upload)</dt>
                <dd className="mt-1 text-3xl font-semibold text-gray-900">{formatBytes(realtime?.total_upload || 0)}</dd>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Top Users Chart */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Топ пользователей (GB)</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    layout="vertical"
                    data={topUsers}
                    margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={100} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="traffic" fill="#8884d8" name="Трафик (GB)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Traffic by Server Chart */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Трафик по серверам (GB)</h3>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={byServer}
                    margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="traffic" fill="#82ca9d" name="Трафик (GB)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Up/Down Distribution */}
            <div className="bg-white shadow rounded-lg p-6 lg:col-span-2">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Распределение Download / Upload</h3>
              <div className="h-80 flex justify-center">
                 <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={100}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={index === 0 ? '#10B981' : '#3B82F6'} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => formatBytes(value)} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

export default Traffic;
