import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL}/api` 
  : 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor для добавления токена
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor для обработки ошибок
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: async (username: string, password: string) => {
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);
    
    const response = await axios.post(`${API_BASE_URL}/auth/login`, params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },
  
  logout: async () => {
    const response = await api.post('/auth/logout');
    return response.data;
  },
  
  getCurrentUser: async () => {
    const response = await api.get('/auth/me');
    return response.data;
  },
};

// Users API
export const usersAPI = {
  getAll: async () => {
    const response = await api.get('/users');
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await api.get(`/users/${id}`);
    return response.data;
  },
  
  create: async (data: { username: string; email?: string; password: string }) => {
    const response = await api.post('/users', data);
    return response.data;
  },
  
  update: async (id: number, data: { email?: string; password?: string; is_active?: boolean }) => {
    const response = await api.put(`/users/${id}`, data);
    return response.data;
  },
  
  delete: async (id: number) => {
    await api.delete(`/users/${id}`);
  },
};

// VPN Clients API
export const vpnClientsAPI = {
  getAll: async () => {
    const response = await api.get('/vpn-clients');
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await api.get(`/vpn-clients/${id}`);
    return response.data;
  },
  
  create: async (data: { name: string; email?: string; notes?: string; is_active?: boolean }) => {
    const response = await api.post('/vpn-clients', data);
    return response.data;
  },
  
  update: async (id: number, data: { name?: string; email?: string; notes?: string; is_active?: boolean }) => {
    const response = await api.put(`/vpn-clients/${id}`, data);
    return response.data;
  },
  
  delete: async (id: number) => {
    await api.delete(`/vpn-clients/${id}`);
  },
};

// Servers API
export const serversAPI = {
  getAll: async () => {
    const response = await api.get('/servers');
    return response.data;
  },
  
  getById: async (id: number) => {
    const response = await api.get(`/servers/${id}`);
    return response.data;
  },
  
  create: async (data: {
    name: string;
    host: string;
    port: number;
    ssh_user: string;
    ssh_password?: string;
    ssh_key_path?: string;
  }) => {
    const response = await api.post('/servers', data);
    return response.data;
  },
  
  update: async (id: number, data: any) => {
    const response = await api.put(`/servers/${id}`, data);
    return response.data;
  },
  
  delete: async (id: number) => {
    await api.delete(`/servers/${id}`);
  },
  
  getConfigs: async (id: number) => {
    const response = await api.get(`/servers/${id}/configs`);
    return response.data;
  },

  fetchUsers: async (id: number) => {
    const response = await api.get(`/servers/${id}/fetch-users`);
    return response.data;
  },
};

// Configs API
export const configsAPI = {
  getAll: async (serverId?: number, clientId?: number) => {
    const params = new URLSearchParams();
    if (serverId) params.append('server_id', serverId.toString());
    if (clientId) params.append('client_id', clientId.toString());
    const response = await api.get(`/configs/?${params.toString()}`);
    return response.data;
  },

  getById: async (id: number) => {
    const response = await api.get(`/configs/${id}`);
    return response.data;
  },

  create: async (data: {
    client_id: number;
    server_id: number;
    device_name: string;
    protocol: string;
    config_content: string;
    peer_public_key?: string;
    client_uuid?: string;
    client_email?: string;
    endpoint?: string | null;
    allowed_ips?: string | null;
  }) => {
    const response = await api.post('/configs', data);
    return response.data;
  },

  update: async (id: number, data: {
    device_name?: string;
    is_active?: boolean;
    config_content?: string;
  }) => {
    const response = await api.put(`/configs/${id}`, data);
    return response.data;
  },

  getQRCode: async (id: number, format: 'standard' | 'amnezia' = 'standard') => {
    const response = await api.get(`/configs/${id}/qrcode?format=${format}`, {
      responseType: 'blob',
    });
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/configs/${id}`);
  },

  toggleActive: async (id: number) => {
    const response = await api.post(`/configs/${id}/toggle-active`);
    return response.data;
  },

  bulkCreate: async (data: {
    client_id: number;
    server_id: number;
    protocol: string;
    count: number;
    device_name_prefix?: string;
    config_content_template?: string;
  }) => {
    const response = await api.post('/configs/bulk', data);
    return response.data;
  },

  getSharingAlerts: async () => {
    const response = await api.get('/configs/sharing-alerts');
    return response.data;
  },

  getEndpointHistory: async (id: number) => {
    const response = await api.get(`/configs/${id}/endpoint-history`);
    return response.data;
  },

  getSharingStatus: async (id: number) => {
    const response = await api.get(`/configs/${id}/sharing-status`);
    return response.data;
  },
};

// Traffic API
export const trafficAPI = {
  getRealtime: async (serverId?: number, clientId?: number) => {
    const params = new URLSearchParams();
    if (serverId) params.append('server_id', serverId.toString());
    if (clientId) params.append('client_id', clientId.toString());
    
    const response = await api.get(`/traffic/realtime?${params.toString()}`);
    return response.data;
  },
  
  getTopUsers: async (limit = 10, serverId?: number) => {
    let url = `/traffic/top-users?limit=${limit}`;
    if (serverId) url += `&server_id=${serverId}`;
    const response = await api.get(url);
    return response.data;
  },

  getByServer: async () => {
    const response = await api.get('/traffic/by-server');
    return response.data;
  },
};

// Subscription Plans API
export const subscriptionPlansAPI = {
  getAll: async (activeOnly = false) => {
    const response = await api.get(`/subscription-plans?active_only=${activeOnly}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/subscription-plans', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/subscription-plans/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/subscription-plans/${id}`);
  },
};

// Subscriptions API
export const subscriptionsAPI = {
  getAll: async (skip = 0, limit = 100) => {
    const response = await api.get(`/subscriptions?skip=${skip}&limit=${limit}`);
    return response.data;
  },

  create: async (data: {
    client_id?: number;
    config_id?: number;
    plan_id: number;
  }) => {
    const response = await api.post('/subscriptions', data);
    return response.data;
  },

  update: async (id: number, data: { is_active?: boolean; traffic_limit_gb?: number; subscription_end?: string; plan_id?: number }) => {
    const response = await api.put(`/subscriptions/${id}`, data);
    return response.data;
  },

  extend: async (id: number, days: number) => {
    const response = await api.post(`/subscriptions/${id}/extend?days=${days}`);
    return response.data;
  },

  delete: async (id: number) => {
    await api.delete(`/subscriptions/${id}`);
  },
};

export default api;
