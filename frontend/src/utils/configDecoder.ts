/**
 * VPN config decoder
 * Supports: vpn:// (AmneziaVPN), vless://, vmess://, trojan://, ss://
 */

export interface DecodedConfig {
  format: 'amnezia' | 'vless' | 'vmess' | 'trojan' | 'shadowsocks' | 'openvpn' | 'unknown';
  protocol: string;
  server: string;
  port: number;
  uuid?: string;
  password?: string;
  flow?: string;
  security?: string;
  sni?: string;
  shortId?: string;
  publicKey?: string;
  fingerprint?: string;
  network?: string;
  description?: string;
  raw?: any;
  vlessUrl?: string;
}

/** base64url → Uint8Array */
function base64urlToBytes(str: string): Uint8Array {
  const padded = str + '='.repeat((4 - (str.length % 4)) % 4);
  const b64 = padded.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(b64);
  return Uint8Array.from(binary, c => c.charCodeAt(0));
}

/** Zlib decompress using browser DecompressionStream (zlib header at bytes 4+) */
async function zlibDecompress(data: Uint8Array): Promise<string> {
  const ds = new DecompressionStream('deflate');
  const writer = ds.writable.getWriter();
  const reader = ds.readable.getReader();

  writer.write(data);
  writer.close();

  const chunks: Uint8Array[] = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
  }

  const total = chunks.reduce((acc, c) => acc + c.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return new TextDecoder().decode(result);
}

/** Decode AmneziaVPN vpn:// format */
async function decodeAmnezia(raw: string): Promise<DecodedConfig> {
  const bytes = base64urlToBytes(raw);
  // Find zlib magic bytes within the first 20 bytes of the header.
  // AmneziaVPN prepends a custom header (length varies by version: 4 or 12 bytes).
  // Valid zlib starts with 0x78 followed by 0x01, 0x5E, 0x9C, or 0xDA.
  const zlibMagicSecondBytes = new Set([0x01, 0x5E, 0x9C, 0xDA]);
  let zlibOffset = 4; // fallback
  for (let i = 0; i < Math.min(bytes.length - 1, 20); i++) {
    if (bytes[i] === 0x78 && zlibMagicSecondBytes.has(bytes[i + 1])) {
      zlibOffset = i;
      break;
    }
  }
  const compressed = bytes.slice(zlibOffset);
  const json = await zlibDecompress(compressed);
  const outer = JSON.parse(json);

  const container = outer.containers?.[0];
  const description = outer.description || '';

  if (!container) throw new Error('No container found in AmneziaVPN config');

  const containerName: string = container.container || '';

  // XRay / VLESS / VMess
  if (containerName.includes('xray') || container.xray) {
    const lastConfigStr = container.xray?.last_config;
    if (!lastConfigStr) throw new Error('No xray config found');

    const xrayConfig = JSON.parse(lastConfigStr);

    // Client config — UUID in outbounds
    for (const ob of xrayConfig.outbounds || []) {
      const proto: string = ob.protocol || '';
      if (['vless', 'vmess', 'trojan'].includes(proto)) {
        const vnext = ob.settings?.vnext?.[0];
        const user = vnext?.users?.[0];
        const ss = ob.streamSettings || {};
        const reality = ss.realitySettings || {};
        const tls = ss.tlsSettings || {};

        const result: DecodedConfig = {
          format: 'amnezia',
          protocol: proto,
          server: vnext?.address || '',
          port: vnext?.port || 443,
          uuid: user?.id,
          flow: user?.flow,
          security: ss.security,
          sni: reality.serverName || tls.serverName,
          shortId: reality.shortId,
          publicKey: reality.publicKey,
          fingerprint: reality.fingerprint || ss.fingerprint,
          network: ss.network,
          description,
          raw: outer,
        };

        // Generate vless:// URL for easy copy
        if (proto === 'vless' && result.uuid && result.server) {
          const params = new URLSearchParams();
          if (result.security) params.set('security', result.security);
          if (result.sni) params.set('sni', result.sni);
          if (result.fingerprint) params.set('fp', result.fingerprint);
          if (result.publicKey) params.set('pbk', result.publicKey);
          if (result.shortId) params.set('sid', result.shortId);
          if (result.flow) params.set('flow', result.flow);
          if (result.network) params.set('type', result.network);
          result.vlessUrl = `vless://${result.uuid}@${result.server}:${result.port}?${params.toString()}#${encodeURIComponent(description)}`;
        }

        return result;
      }
    }

    // Server config — UUID in inbounds
    for (const ib of xrayConfig.inbounds || []) {
      const proto: string = ib.protocol || '';
      if (['vless', 'vmess', 'trojan'].includes(proto)) {
        const clients = ib.settings?.clients || [];
        const ss = ib.streamSettings || {};
        const reality = ss.realitySettings || {};
        return {
          format: 'amnezia',
          protocol: proto,
          server: '',
          port: ib.port || 443,
          uuid: clients[0]?.id,
          flow: clients[0]?.flow,
          security: ss.security,
          sni: reality.serverNames?.[0],
          description: description + ' (server config)',
          raw: outer,
        };
      }
    }
  }

  // WireGuard / AWG
  if (containerName.includes('wireguard') || containerName.includes('awg') || container.wireguard || container.awg) {
    const wgConfig = container.wireguard?.last_config || container.awg?.last_config || '';
    const serverMatch = wgConfig.match(/Endpoint\s*=\s*([^\s:]+):(\d+)/i);
    const uuidMatch = wgConfig.match(/PrivateKey\s*=\s*([^\s]+)/i);
    return {
      format: 'amnezia',
      protocol: containerName.includes('awg') ? 'awg' : 'wireguard',
      server: serverMatch?.[1] || '',
      port: parseInt(serverMatch?.[2] || '51820'),
      uuid: uuidMatch?.[1],
      description,
      raw: outer,
    };
  }

  // OpenVPN / AmneziaOpenVPN
  if (containerName.includes('openvpn') || container.openvpn) {
    const ovpnConfig: string = container.openvpn?.last_config || '';
    const serverMatch = ovpnConfig.match(/^remote\s+([^\s]+)\s+(\d+)/im);
    return {
      format: 'amnezia',
      protocol: 'openvpn',
      server: serverMatch?.[1] || '',
      port: parseInt(serverMatch?.[2] || '1194'),
      description,
      raw: outer,
    };
  }

  throw new Error(`Unknown container type: ${containerName}`);
}

/** Decode vless://UUID@host:port?params#name */
function decodeVless(url: string): DecodedConfig {
  const u = new URL(url);
  const params = u.searchParams;
  return {
    format: 'vless',
    protocol: 'vless',
    server: u.hostname,
    port: parseInt(u.port) || 443,
    uuid: u.username,
    flow: params.get('flow') || undefined,
    security: params.get('security') || undefined,
    sni: params.get('sni') || undefined,
    publicKey: params.get('pbk') || undefined,
    shortId: params.get('sid') || undefined,
    fingerprint: params.get('fp') || undefined,
    network: params.get('type') || undefined,
    description: decodeURIComponent(u.hash.replace('#', '')),
    vlessUrl: url,
  };
}

/** Decode vmess://base64JSON */
function decodeVmess(raw: string): DecodedConfig {
  const json = JSON.parse(atob(raw));
  return {
    format: 'vmess',
    protocol: 'vmess',
    server: json.add || '',
    port: parseInt(json.port) || 443,
    uuid: json.id,
    network: json.net,
    sni: json.host || json.sni,
    security: json.tls || undefined,
    description: json.ps,
  };
}

/** Decode trojan://password@host:port?params#name */
function decodeTrojan(url: string): DecodedConfig {
  const u = new URL(url);
  const params = u.searchParams;
  return {
    format: 'trojan',
    protocol: 'trojan',
    server: u.hostname,
    port: parseInt(u.port) || 443,
    password: u.username,
    security: params.get('security') || 'tls',
    sni: params.get('sni') || params.get('peer') || undefined,
    network: params.get('type') || 'tcp',
    description: decodeURIComponent(u.hash.replace('#', '')),
  };
}

/** Decode ss://base64@host:port#name or ss://method:password@host:port#name */
function decodeShadowsocks(url: string): DecodedConfig {
  const u = new URL(url);
  let method = '', password = '';
  if (u.username && u.password) {
    method = decodeURIComponent(u.username);
    password = decodeURIComponent(u.password);
  } else if (u.username) {
    try {
      const decoded = atob(u.username);
      const colonIdx = decoded.indexOf(':');
      method = decoded.substring(0, colonIdx);
      password = decoded.substring(colonIdx + 1);
    } catch {
      password = u.username;
    }
  }
  return {
    format: 'shadowsocks',
    protocol: 'shadowsocks',
    server: u.hostname,
    port: parseInt(u.port) || 8388,
    password,
    description: decodeURIComponent(u.hash.replace('#', '')) || method,
  };
}

/** Main decode function — auto-detect format */
export async function decodeConfig(input: string): Promise<DecodedConfig> {
  const trimmed = input.trim();

  if (trimmed.startsWith('vpn://')) {
    return decodeAmnezia(trimmed.replace('vpn://', ''));
  }
  if (trimmed.startsWith('vless://')) {
    return decodeVless(trimmed);
  }
  if (trimmed.startsWith('vmess://')) {
    return decodeVmess(trimmed.replace('vmess://', ''));
  }
  if (trimmed.startsWith('trojan://')) {
    return decodeTrojan(trimmed);
  }
  if (trimmed.startsWith('ss://')) {
    return decodeShadowsocks(trimmed);
  }

  // Try to decode as raw AmneziaVPN base64 (without vpn:// prefix)
  const noWhitespace = trimmed.replace(/\s+/g, '');
  if (/^[A-Za-z0-9+/\-_]+=*$/.test(noWhitespace) && noWhitespace.length > 20) {
    try {
      return await decodeAmnezia(noWhitespace);
    } catch (e) {
      throw new Error(`Failed to decode AmneziaVPN config: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  throw new Error('Unknown config format. Supported: vpn://, vless://, vmess://, trojan://, ss://');
}

/** Read QR code from image File using jsQR + canvas */
export async function decodeQR(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(img, 0, 0);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);

      import('jsqr').then(({ default: jsQR }) => {
        const result = jsQR(imageData.data, imageData.width, imageData.height);
        if (result) {
          resolve(result.data);
        } else {
          reject(new Error('QR code not found in image'));
        }
      }).catch(reject);
    };
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = url;
  });
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}
