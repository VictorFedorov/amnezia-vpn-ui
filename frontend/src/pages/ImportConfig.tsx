import { useState, useRef } from 'react';
import Layout from '../components/Layout';
import { decodeConfig, decodeQR, type DecodedConfig } from '../utils/configDecoder';

const PROTOCOL_LABELS: Record<string, string> = {
  vless: 'VLESS',
  vmess: 'VMess',
  trojan: 'Trojan',
  shadowsocks: 'Shadowsocks',
  awg: 'AmneziaWG',
  wireguard: 'WireGuard',
};

const PROTOCOL_COLORS: Record<string, string> = {
  vless: 'bg-purple-100 text-purple-800',
  vmess: 'bg-blue-100 text-blue-800',
  trojan: 'bg-red-100 text-red-800',
  shadowsocks: 'bg-orange-100 text-orange-800',
  awg: 'bg-teal-100 text-teal-800',
  wireguard: 'bg-green-100 text-green-800',
};

export default function ImportConfig() {
  const [inputText, setInputText] = useState('');
  const [decoded, setDecoded] = useState<DecodedConfig | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDecode = async (text: string) => {
    if (!text.trim()) return;
    setLoading(true);
    setError('');
    setDecoded(null);
    try {
      const result = await decodeConfig(text.trim());
      setDecoded(result);
    } catch (e: any) {
      setError(e.message || 'Failed to decode config');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError('');
    setDecoded(null);
    try {
      const qrText = await decodeQR(file);
      setInputText(qrText);
      await handleDecode(qrText);
    } catch (e: any) {
      setError(e.message || 'Failed to read QR code');
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleClear = () => {
    setInputText('');
    setDecoded(null);
    setError('');
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Импорт конфигурации</h1>

        {/* Input area */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Вставьте конфиг или ссылку
          </label>
          <textarea
            className="w-full h-28 px-3 py-2 text-sm font-mono border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="vpn://... или vless://... или vmess://... или trojan://... или ss://..."
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) handleDecode(inputText); }}
          />
          <div className="flex items-center gap-3 mt-3">
            <button
              onClick={() => handleDecode(inputText)}
              disabled={loading || !inputText.trim()}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Декодирование...' : 'Декодировать'}
            </button>

            {/* QR upload */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={loading}
              className="px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200 disabled:opacity-50 flex items-center gap-2"
            >
              <span>📷</span> Загрузить QR
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleFileUpload}
            />

            {(decoded || error) && (
              <button
                onClick={handleClear}
                className="ml-auto text-sm text-gray-500 hover:text-gray-700"
              >
                Очистить
              </button>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Поддерживаемые форматы: <span className="font-mono">vpn://</span> (AmneziaVPN), <span className="font-mono">vless://</span>, <span className="font-mono">vmess://</span>, <span className="font-mono">trojan://</span>, <span className="font-mono">ss://</span>
          </p>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 text-sm text-red-700">
            ❌ {error}
          </div>
        )}

        {/* Decoded result */}
        {decoded && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${PROTOCOL_COLORS[decoded.protocol] || 'bg-gray-100 text-gray-800'}`}>
                    {PROTOCOL_LABELS[decoded.protocol] || decoded.protocol.toUpperCase()}
                  </span>
                  <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
                    {decoded.format === 'amnezia' ? 'AmneziaVPN конфиг' : 'Стандартная ссылка'}
                  </span>
                </div>
              </div>
            </div>

            {/* Server info */}
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Сервер</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <InfoRow label="Название" value={decoded.description || '—'} />
                </div>
                <InfoRow label="Адрес" value={decoded.server || '—'} mono />
                <InfoRow label="Порт" value={decoded.port?.toString() || '—'} mono />
                {decoded.sni && <InfoRow label="SNI" value={decoded.sni} mono />}
                {decoded.security && <InfoRow label="Security" value={decoded.security} mono />}
                {decoded.network && <InfoRow label="Network" value={decoded.network} mono />}
                {decoded.fingerprint && <InfoRow label="Fingerprint" value={decoded.fingerprint} mono />}
              </div>
            </div>

            {/* Client credentials */}
            <div>
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Идентификатор клиента</h3>
              <div className="space-y-2">
                {decoded.uuid && (
                  <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                    <div>
                      <span className="text-xs text-gray-500 block">UUID</span>
                      <span className="text-sm font-mono text-gray-900">{decoded.uuid}</span>
                    </div>
                    <button
                      onClick={() => handleCopy(decoded.uuid!)}
                      className="text-xs text-blue-600 hover:text-blue-800 ml-3 shrink-0"
                    >
                      {copied ? '✓' : 'Копировать'}
                    </button>
                  </div>
                )}
                {decoded.password && (
                  <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                    <div>
                      <span className="text-xs text-gray-500 block">Password</span>
                      <span className="text-sm font-mono text-gray-900">{decoded.password}</span>
                    </div>
                    <button
                      onClick={() => handleCopy(decoded.password!)}
                      className="text-xs text-blue-600 hover:text-blue-800 ml-3 shrink-0"
                    >
                      {copied ? '✓' : 'Копировать'}
                    </button>
                  </div>
                )}
                {decoded.flow && <InfoRow label="Flow" value={decoded.flow} mono />}
                {decoded.publicKey && (
                  <div className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                    <div>
                      <span className="text-xs text-gray-500 block">Public Key</span>
                      <span className="text-sm font-mono text-gray-900 break-all">{decoded.publicKey}</span>
                    </div>
                    <button
                      onClick={() => handleCopy(decoded.publicKey!)}
                      className="text-xs text-blue-600 hover:text-blue-800 ml-3 shrink-0"
                    >
                      {copied ? '✓' : 'Копировать'}
                    </button>
                  </div>
                )}
                {decoded.shortId && <InfoRow label="Short ID" value={decoded.shortId} mono />}
              </div>
            </div>

            {/* vless:// URL */}
            {decoded.vlessUrl && (
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">VLESS URL</h3>
                <div className="flex items-start gap-2 bg-gray-50 rounded-lg px-3 py-2">
                  <span className="text-xs font-mono text-gray-700 break-all flex-1">{decoded.vlessUrl}</span>
                  <button
                    onClick={() => handleCopy(decoded.vlessUrl!)}
                    className="text-xs text-blue-600 hover:text-blue-800 shrink-0"
                  >
                    {copied ? '✓' : 'Копировать'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  );
}

function InfoRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2">
      <span className="text-xs text-gray-500 block">{label}</span>
      <span className={`text-sm text-gray-900 ${mono ? 'font-mono' : ''}`}>{value}</span>
    </div>
  );
}
