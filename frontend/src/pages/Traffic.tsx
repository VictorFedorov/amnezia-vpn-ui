import { useEffect, useState, useCallback } from 'react';
import Layout from '../components/Layout';
import { trafficAPI } from '../services/api';
import type { TrafficPeriod } from '../services/api';
import {
  AreaChart, Area,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

const PERIODS: { value: TrafficPeriod; label: string }[] = [
  { value: 'day',     label: 'День' },
  { value: 'week',    label: 'Неделя' },
  { value: 'month',   label: 'Месяц' },
  { value: 'quarter', label: 'Квартал' },
  { value: 'year',    label: 'Год' },
];

function formatBytes(bytes: number): string {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatBucket(bucket: string, period: TrafficPeriod): string {
  if (!bucket) return '';
  if (period === 'day') {
    // "2024-03-08 14:00:00" → "14:00"
    return bucket.slice(11, 16);
  }
  if (period === 'year') {
    // "2024-03" → "Мар 2024"
    const [year, month] = bucket.split('-');
    const date = new Date(Number(year), Number(month) - 1);
    return date.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' });
  }
  if (period === 'quarter') {
    // "2024-10" (ISO week) → "W10"
    return `W${bucket.split('-')[1]}`;
  }
  // week / month: "2024-03-08" → "08.03"
  const parts = bucket.split('-');
  return `${parts[2]}.${parts[1]}`;
}

interface HistoryPoint {
  bucket: string;
  label: string;
  download: number;
  upload: number;
  downloadGB: number;
  uploadGB: number;
}

interface Summary {
  total_download: number;
  total_upload: number;
  total: number;
  active_configs: number;
}

function Traffic() {
  const [period, setPeriod] = useState<TrafficPeriod>('week');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [topUsers, setTopUsers] = useState<{ name: string; trafficGB: number }[]>([]);
  const [byServer, setByServer] = useState<{ name: string; trafficGB: number }[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async (p: TrafficPeriod) => {
    setLoading(true);
    try {
      const [summaryData, historyData, usersData, serverData] = await Promise.all([
        trafficAPI.getSummary(p),
        trafficAPI.getHistory(p),
        trafficAPI.getTopUsers(10, undefined, p),
        trafficAPI.getByServer(p),
      ]);

      setSummary(summaryData);

      setHistory(
        historyData.map((r: { bucket: string; download: number; upload: number }) => ({
          bucket: r.bucket,
          label: formatBucket(r.bucket, p),
          download: r.download,
          upload: r.upload,
          downloadGB: parseFloat((r.download / 1073741824).toFixed(3)),
          uploadGB: parseFloat((r.upload / 1073741824).toFixed(3)),
        }))
      );

      setTopUsers(
        usersData.map((u: { username: string; total_traffic: number }) => ({
          name: u.username,
          trafficGB: parseFloat((u.total_traffic / 1073741824).toFixed(2)),
        }))
      );

      setByServer(
        serverData.map((s: { server_name: string; total_traffic: number }) => ({
          name: s.server_name,
          trafficGB: parseFloat((s.total_traffic / 1073741824).toFixed(2)),
        }))
      );
    } catch (err) {
      console.error('Failed to load traffic data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(period);
  }, [period, loadData]);

  const noHistory = !loading && history.length === 0;

  return (
    <Layout>
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">

          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Трафик</h1>
            <div className="flex items-center gap-2">
              {PERIODS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setPeriod(value)}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    period === value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <SummaryCard
              label="Всего за период"
              value={summary ? formatBytes(summary.total) : '—'}
              color="gray"
              loading={loading}
            />
            <SummaryCard
              label="Загружено"
              value={summary ? formatBytes(summary.total_download) : '—'}
              color="green"
              loading={loading}
            />
            <SummaryCard
              label="Отдано"
              value={summary ? formatBytes(summary.total_upload) : '—'}
              color="blue"
              loading={loading}
            />
            <SummaryCard
              label="Активных устройств"
              value={summary ? String(summary.active_configs) : '—'}
              color="purple"
              loading={loading}
            />
          </div>

          {/* Area chart */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Динамика трафика
            </h2>
            {noHistory ? (
              <EmptyState />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={history} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="colorDown" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorUp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                  <YAxis
                    tickFormatter={(v) => `${v} GB`}
                    tick={{ fontSize: 12 }}
                    width={60}
                  />
                  <Tooltip
                    formatter={(value: number | undefined, name: string | undefined) => [
                      `${(value ?? 0).toFixed(3)} GB`,
                      name === 'downloadGB' ? 'Download' : 'Upload',
                    ]}
                    labelFormatter={(label) => `Период: ${label}`}
                  />
                  <Legend
                    formatter={(value) => value === 'downloadGB' ? 'Download' : 'Upload'}
                  />
                  <Area
                    type="monotone"
                    dataKey="downloadGB"
                    stroke="#10B981"
                    fill="url(#colorDown)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="uploadGB"
                    stroke="#3B82F6"
                    fill="url(#colorUp)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Bottom row: top users + by server */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Топ пользователей (GB)
              </h2>
              {topUsers.length === 0 ? (
                <EmptyState />
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    layout="vertical"
                    data={topUsers}
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" tickFormatter={(v) => `${v} GB`} tick={{ fontSize: 11 }} />
                    <YAxis dataKey="name" type="category" width={90} tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number | undefined) => [`${v ?? 0} GB`, 'Трафик']} />
                    <Bar dataKey="trafficGB" fill="#8B5CF6" name="Трафик (GB)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                По серверам (GB)
              </h2>
              {byServer.length === 0 ? (
                <EmptyState />
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart
                    data={byServer}
                    margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tickFormatter={(v) => `${v} GB`} tick={{ fontSize: 11 }} width={55} />
                    <Tooltip formatter={(v: number | undefined) => [`${v ?? 0} GB`, 'Трафик']} />
                    <Bar dataKey="trafficGB" fill="#F59E0B" name="Трафик (GB)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

        </div>
      </div>
    </Layout>
  );
}

function SummaryCard({ label, value, color, loading }: {
  label: string; value: string; color: string; loading: boolean;
}) {
  const colors: Record<string, string> = {
    gray: 'text-gray-900',
    green: 'text-green-600',
    blue: 'text-blue-600',
    purple: 'text-purple-600',
  };
  return (
    <div className="bg-white shadow rounded-lg px-4 py-5">
      <dt className="text-sm font-medium text-gray-500 truncate">{label}</dt>
      <dd className={`mt-1 text-2xl font-bold ${colors[color] ?? 'text-gray-900'}`}>
        {loading ? <span className="animate-pulse text-gray-300">···</span> : value}
      </dd>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-gray-400">
      <svg className="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
      <p className="text-sm">Нет данных за этот период</p>
      <p className="text-xs mt-1">История трафика накапливается при каждой синхронизации</p>
    </div>
  );
}

export default Traffic;
