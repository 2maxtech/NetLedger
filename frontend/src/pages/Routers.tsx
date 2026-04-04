import { useState } from 'react';
import {
  Table, Card, Button, Modal, Form, Input, Switch, Typography,
  Popconfirm, Space, message, Tag, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CloudServerOutlined,
  ImportOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getRouters, createRouter, updateRouter, deleteRouter,
  getRouterStatus, importFromRouter, scanNetwork,
  type RouterType, type RouterStatus,
} from '../api/routers';

const Routers = () => {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRouter, setEditingRouter] = useState<RouterType | null>(null);
  const [scanOpen, setScanOpen] = useState(false);
  const [scanResults, setScanResults] = useState<any[]>([]);
  const [form] = Form.useForm();
  const [scanForm] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['routers'],
    queryFn: () => getRouters().then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: createRouter,
    onSuccess: () => {
      message.success('Router added');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
    onError: () => message.error('Failed to add router'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateRouter(id, data),
    onSuccess: () => {
      message.success('Router updated');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
    onError: () => message.error('Failed to update router'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteRouter,
    onSuccess: () => {
      message.success('Router removed');
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
    onError: () => message.error('Failed to remove router'),
  });

  const scanMut = useMutation({
    mutationFn: scanNetwork,
    onSuccess: (res) => {
      setScanResults(res.data?.found || []);
      message.success(`Found ${res.data?.found?.length || 0} device(s)`);
    },
    onError: () => message.error('Scan failed'),
  });

  const importMut = useMutation({
    mutationFn: importFromRouter,
    onSuccess: (res) => {
      message.success(
        `Imported ${res.data?.imported || 0} users, updated ${res.data?.updated || 0}`,
      );
      queryClient.invalidateQueries({ queryKey: ['routers'] });
    },
    onError: () => message.error('Import failed'),
  });

  const closeModal = () => {
    setModalOpen(false);
    setEditingRouter(null);
    form.resetFields();
  };

  const openEdit = (router: RouterType) => {
    setEditingRouter(router);
    form.setFieldsValue({
      name: router.name,
      url: router.url,
      username: router.username,
      location: router.location,
      maintenance_mode: router.maintenance_mode,
      maintenance_message: router.maintenance_message,
    });
    setModalOpen(true);
  };

  const onFinish = (values: any) => {
    if (editingRouter) updateMut.mutate({ id: editingRouter.id, data: values });
    else createMut.mutate(values);
  };

  const testConnection = async (id: string) => {
    try {
      const res = await getRouterStatus(id);
      const status: RouterStatus = res.data;
      if (status.connected) {
        message.success(
          `Connected — ${status.identity} | Uptime: ${status.uptime} | CPU: ${status.cpu_load}`,
        );
      } else {
        message.error(`Connection failed: ${status.error || 'Unknown error'}`);
      }
    } catch {
      message.error('Failed to test connection');
    }
  };

  const scanColumns = [
    { title: 'IP Address', dataIndex: 'ip', key: 'ip' },
    { title: 'MAC', dataIndex: 'mac', key: 'mac' },
    { title: 'Hostname', dataIndex: 'hostname', key: 'hostname' },
    {
      title: '',
      key: 'add',
      render: (_: unknown, rec: any) => (
        <Button
          size="small"
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setScanOpen(false);
            form.setFieldsValue({ url: `http://${rec.ip}`, name: rec.hostname || rec.ip });
            setModalOpen(true);
          }}
        >
          Add
        </Button>
      ),
    },
  ];

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'URL', dataIndex: 'url', key: 'url', ellipsis: true },
    { title: 'Location', dataIndex: 'location', key: 'location', render: (v: string | null) => v || '-' },
    {
      title: 'Status',
      key: 'status',
      render: (_: unknown, r: RouterType) => (
        <Tag color={r.is_active ? '#10b981' : '#6b7280'}>
          {r.is_active ? 'Active' : 'Inactive'}
        </Tag>
      ),
      width: 90,
    },
    {
      title: 'Maintenance',
      key: 'maintenance',
      render: (_: unknown, r: RouterType) =>
        r.maintenance_mode ? (
          <Tooltip title={r.maintenance_message || ''}>
            <Tag color="#f59e0b">Maintenance</Tag>
          </Tooltip>
        ) : null,
      width: 120,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 180,
      render: (_: unknown, r: RouterType) => (
        <Space size="small">
          <Button size="small" icon={<ThunderboltOutlined />} onClick={() => testConnection(r.id)}>
            Test
          </Button>
          <Popconfirm
            title="Import PPPoE users from this router?"
            onConfirm={() => importMut.mutate(r.id)}
          >
            <Button size="small" icon={<ImportOutlined />} loading={importMut.isPending}>
              Import
            </Button>
          </Popconfirm>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Popconfirm title="Remove this router?" onConfirm={() => deleteMut.mutate(r.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <CloudServerOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Routers
        </Typography.Title>
        <Space>
          <Button icon={<CloudServerOutlined />} onClick={() => setScanOpen(true)}>
            Scan Network
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            Add Router
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          dataSource={data || []}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={false}
        />
      </Card>

      {/* Add / Edit Modal */}
      <Modal
        title={editingRouter ? 'Edit Router' : 'Add Router'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={createMut.isPending || updateMut.isPending}
      >
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="url" label="URL (e.g. http://192.168.88.1)" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="username" label="Username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: !editingRouter }]}>
            <Input.Password placeholder={editingRouter ? 'Leave blank to keep current' : ''} />
          </Form.Item>
          <Form.Item name="location" label="Location">
            <Input />
          </Form.Item>
          <Form.Item name="maintenance_mode" label="Maintenance Mode" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="maintenance_message" label="Maintenance Message">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Scan Network Modal */}
      <Modal
        title="Scan Network"
        open={scanOpen}
        onCancel={() => { setScanOpen(false); setScanResults([]); scanForm.resetFields(); }}
        footer={null}
        width={700}
      >
        <Form
          form={scanForm}
          layout="inline"
          style={{ marginBottom: 16 }}
          onFinish={(values) => scanMut.mutate(values)}
        >
          <Form.Item name="subnet" label="Subnet" rules={[{ required: true }]}>
            <Input placeholder="192.168.88.0/24" style={{ width: 180 }} />
          </Form.Item>
          <Form.Item name="username" label="Username">
            <Input placeholder="admin" />
          </Form.Item>
          <Form.Item name="password" label="Password">
            <Input.Password />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={scanMut.isPending}
              icon={<CloudServerOutlined />}
            >
              Scan
            </Button>
          </Form.Item>
        </Form>
        {scanResults.length > 0 && (
          <Table
            dataSource={scanResults}
            columns={scanColumns}
            rowKey="ip"
            size="small"
            pagination={false}
          />
        )}
      </Modal>
    </div>
  );
};

export default Routers;
