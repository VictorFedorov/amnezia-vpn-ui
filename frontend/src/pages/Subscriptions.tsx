import { useEffect, useState } from 'react';
import Layout from '../components/Layout';
import { subscriptionsAPI, usersAPI, subscriptionPlansAPI, configsAPI, vpnClientsAPI } from '../services/api';

function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [configs, setConfigs] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showExtendModal, setShowExtendModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingSub, setEditingSub] = useState<any>(null);
  const [editFormData, setEditFormData] = useState({
    subscription_end: '',
    is_active: true,
    traffic_limit_gb: 0,
    plan_id: '',
  });
  const [formData, setFormData] = useState({
    client_id: '',
    config_id: '',
    plan_id: '',
  });
  const [extendDays, setExtendDays] = useState(30);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [subsData, usersData, plansData, clientsData, configsData] = await Promise.all([
        subscriptionsAPI.getAll(),
        usersAPI.getAll(),
        subscriptionPlansAPI.getAll(true), // Fetch active plans
        vpnClientsAPI.getAll(),
        configsAPI.getAll()
      ]);
      setSubscriptions(subsData);
      setUsers(usersData);
      setPlans(plansData);
      setClients(clientsData);
      setConfigs(configsData);
    } catch (error) {
      console.error('Failed to load subscriptions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.plan_id) {
       alert('Выберите тарифный план');
       return;
    }
    
    try {
      await subscriptionsAPI.create({
        client_id: formData.client_id ? parseInt(formData.client_id) : undefined,
        config_id: formData.config_id ? parseInt(formData.config_id) : undefined,
        plan_id: parseInt(formData.plan_id),
      });
      setShowModal(false);
      resetForm();
      loadData();
    } catch (error) {
      console.error('Failed to create subscription:', error);
      alert('Ошибка при создании подписки');
    }
  };

  const handleExtend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSub) return;
    try {
      await subscriptionsAPI.extend(editingSub.id, extendDays);
      setShowExtendModal(false);
      setEditingSub(null);
      loadData();
    } catch (error) {
      console.error('Failed to extend subscription:', error);
      alert('Ошибка при продлении подписки');
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Вы уверены, что хотите удалить эту подписку?')) return;
    try {
      await subscriptionsAPI.delete(id);
      loadData();
    } catch (error) {
      console.error('Failed to delete subscription:', error);
    }
  };

  const resetForm = () => {
    setFormData({
      client_id: '',
      config_id: '',
      plan_id: '',
    });
  };

  const openExtendModal = (sub: any) => {
    setEditingSub(sub);
    setExtendDays(30);
    setShowExtendModal(true);
  };

  const openEditModal = (sub: any) => {
    setEditingSub(sub);
    // Convert UTC datetime to local date string for input[type=date]
    const endDate = new Date(sub.subscription_end);
    const localDate = endDate.toISOString().split('T')[0];
    setEditFormData({
      subscription_end: localDate,
      is_active: sub.is_active,
      traffic_limit_gb: sub.traffic_limit_gb || 0,
      plan_id: sub.plan_id ? String(sub.plan_id) : '',
    });
    setShowEditModal(true);
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSub) return;
    try {
      await subscriptionsAPI.update(editingSub.id, {
        subscription_end: editFormData.subscription_end
          ? new Date(editFormData.subscription_end + 'T23:59:59').toISOString()
          : undefined,
        is_active: editFormData.is_active,
        traffic_limit_gb: editFormData.traffic_limit_gb || undefined,
        plan_id: editFormData.plan_id ? parseInt(editFormData.plan_id) : undefined,
      });
      setShowEditModal(false);
      setEditingSub(null);
      loadData();
    } catch (error) {
      console.error('Failed to update subscription:', error);
      alert('Ошибка при редактировании подписки');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const isExpired = (endDate: string) => {
    return new Date(endDate) < new Date();
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Управление подписками</h1>
            <button
              onClick={() => { resetForm(); setShowModal(true); }}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
            >
              + Создать подписку
            </button>
          </div>

          <div className="bg-white shadow overflow-hidden sm:rounded-lg">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Клиент / Устройство
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Тариф
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Лимит трафика
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Статус / Дата окончания
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Действия
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {loading ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-4 text-center">Загрузка...</td>
                    </tr>
                  ) : subscriptions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-4 text-center text-gray-500">Подписок нет</td>
                    </tr>
                  ) : (
                    subscriptions.map((sub) => (
                      <tr key={sub.id}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900">
                             {sub.client?.name || sub.client_id || '—'}
                          </div>
                          {sub.client?.email && (
                            <div className="text-sm text-gray-500">{sub.client.email}</div>
                          )}
                          <div className="text-sm text-gray-500">
                             {sub.config ? `Device: ${sub.config.device_name}` : ''}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {sub.plan ? (
                            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 uppercase">
                              {sub.plan.name}
                            </span>
                          ) : (
                             <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800 uppercase">
                              {sub.subscription_type || 'Legacy'}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {sub.traffic_limit_gb ? `${sub.traffic_limit_gb} GB` : 'Безлимит'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex flex-col">
                            <span className={`text-sm font-medium ${sub.is_active ? 'text-green-600' : 'text-red-600'}`}>
                              {sub.is_active ? 'Активна' : 'Неактивна'}
                            </span>
                            <span className={`text-xs ${isExpired(sub.subscription_end) ? 'text-red-500 font-bold' : 'text-gray-500'}`}>
                              до {formatDate(sub.subscription_end)}
                              {isExpired(sub.subscription_end) && ' (Истекла)'}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <button
                            onClick={() => openEditModal(sub)}
                            className="text-gray-600 hover:text-gray-900 mr-4"
                          >
                            Изменить
                          </button>
                          <button
                            onClick={() => openExtendModal(sub)}
                            className="text-indigo-600 hover:text-indigo-900 mr-4"
                          >
                            Продлить
                          </button>
                          <button
                            onClick={() => handleDelete(sub.id)}
                            className="text-red-600 hover:text-red-900"
                          >
                            Удалить
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {showEditModal && editingSub && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-xl w-96">
            <h2 className="text-xl font-bold mb-4">Редактировать подписку</h2>
            <p className="text-sm text-gray-500 mb-4">
              {editingSub.client?.name || `Клиент #${editingSub.client_id}`}
            </p>
            <form onSubmit={handleEdit}>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Дата окончания
                </label>
                <input
                  type="date"
                  className="shadow border rounded w-full py-2 px-3 text-gray-700 focus:outline-none focus:shadow-outline"
                  value={editFormData.subscription_end}
                  onChange={(e) => setEditFormData({ ...editFormData, subscription_end: e.target.value })}
                  required
                />
              </div>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Тарифный план
                </label>
                <select
                  className="shadow border rounded w-full py-2 px-3 text-gray-700 focus:outline-none focus:shadow-outline"
                  value={editFormData.plan_id}
                  onChange={(e) => setEditFormData({ ...editFormData, plan_id: e.target.value })}
                >
                  <option value="">Без изменений</option>
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>{p.name} ({p.duration_days} дн.)</option>
                  ))}
                </select>
              </div>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Лимит трафика (ГБ, 0 = безлимит)
                </label>
                <input
                  type="number"
                  min="0"
                  className="shadow border rounded w-full py-2 px-3 text-gray-700 focus:outline-none focus:shadow-outline"
                  value={editFormData.traffic_limit_gb}
                  onChange={(e) => setEditFormData({ ...editFormData, traffic_limit_gb: parseInt(e.target.value) || 0 })}
                />
              </div>
              <div className="mb-5 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={editFormData.is_active}
                  onChange={(e) => setEditFormData({ ...editFormData, is_active: e.target.checked })}
                  className="w-4 h-4 text-blue-600 rounded"
                />
                <label htmlFor="is_active" className="text-gray-700 text-sm font-bold">
                  Подписка активна
                </label>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                >
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center">
          <div className="bg-white p-5 rounded-lg shadow-xl w-96">
            <h2 className="text-xl font-bold mb-4">Новая подписка</h2>
            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  VPN Клиент (Человек)
                </label>
                <select
                  className="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  value={formData.client_id}
                  onChange={(e) => setFormData({ ...formData, client_id: e.target.value, config_id: '' })}
                >
                  <option value="">Выберите клиента</option>
                  {clients.map((c: any) => (
                    <option key={c.id} value={c.id}>{c.name} {c.email ? `(${c.email})` : ''}</option>
                  ))}
                </select>
              </div>

              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Устройство (Конфигурация)
                </label>
                <select
                  className="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  value={formData.config_id}
                  onChange={(e) => setFormData({ ...formData, config_id: e.target.value })}
                  disabled={!formData.client_id}
                >
                  <option value="">Выберите устройство</option>
                  {configs
                    .filter((c: any) => c.client_id && (!formData.client_id || c.client_id === parseInt(formData.client_id)))
                    .map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.device_name || 'Без названия'} — {c.protocol?.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Тарифный план
                </label>
                <select
                  className="shadow border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  value={formData.plan_id}
                  onChange={(e) => setFormData({ ...formData, plan_id: e.target.value })}
                  required
                >
                  <option value="">Выберите тариф</option>
                  {plans.map((p) => (
                    <option key={p.id} value={p.id}>{p.name} ({p.price} {p.currency}, {p.duration_days} дн.)</option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                >
                  Создать
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Extend Modal */}
      {showExtendModal && editingSub && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center">
          <div className="bg-white p-5 rounded-lg shadow-xl w-96">
            <h2 className="text-xl font-bold mb-4">Продлить подписку</h2>
            <p className="mb-4 text-sm text-gray-600">
             {editingSub.client ? `Клиент: ${editingSub.client.name}` : ''}<br />
              Текущее окончание: {formatDate(editingSub.subscription_end)}
            </p>
            <form onSubmit={handleExtend}>
              <div className="mb-4">
                <label className="block text-gray-700 text-sm font-bold mb-2">
                  Продлить на (дней)
                </label>
                <input
                  type="number"
                  className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                  value={extendDays}
                  onChange={(e) => setExtendDays(parseInt(e.target.value))}
                  required
                />
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowExtendModal(false)}
                  className="bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded"
                >
                  Продлить
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  );
}

export default Subscriptions;
