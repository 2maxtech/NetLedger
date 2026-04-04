import { useState } from 'react';
import {
  Table, Card, Button, Modal, Form, Input, Select,
  Typography, Popconfirm, Space, message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, GlobalOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getRouters } from '../api/routers';
import client from '../api/client';

interface IpPool {
  id: string;
  name: string;
  router_id: string | null;
  subnet: string;
  range_start: string;
  range_end: string;
}

const IPAM = () => {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPool, setEditingPool] = useState<IpPool | null>(null);
  const [form] = Form.useForm();

  const { data: routers } = useQuery({
    queryKey: ['routers'],
    queryFn: () => getRouters().then((r) => r.data),
  });

  const { data, isLoading } = useQuery({
    queryKey: ['ip-pools'],
    queryFn: () => client.get<IpPool[]>('/ipam/pools').then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (payload: any) => client.post('/ipam/pools', payload),
    onSuccess: () => {
      message.success('IP pool created');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['ip-pools'] });
    },
    onError: () => message.error('Failed to create IP pool'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      client.put(`/ipam/pools/${id}`, data),
    onSuccess: () => {
      message.success('IP pool updated');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['ip-pools'] });
    },
    onError: () => message.error('Failed to update IP pool'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => client.delete(`/ipam/pools/${id}`),
    onSuccess: () => {
      message.success('IP pool deleted');
      queryClient.invalidateQueries({ queryKey: ['ip-pools'] });
    },
    onError: () => message.error('Failed to delete IP pool'),
  });

  const closeModal = () => {
    setModalOpen(false);
    setEditingPool(null);
    form.resetFields();
  };

  const openEdit = (pool: IpPool) => {
    setEditingPool(pool);
    form.setFieldsValue(pool);
    setModalOpen(true);
  };

  const onFinish = (values: any) => {
    if (editingPool) updateMut.mutate({ id: editingPool.id, data: values });
    else createMut.mutate(values);
  };

  const routerName = (rid: string | null) => {
    if (!rid) return '-';
    return routers?.find((r) => r.id === rid)?.name || rid.slice(0, 8) + '...';
  };

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Router',
      dataIndex: 'router_id',
      key: 'router',
      render: (rid: string | null) => routerName(rid),
    },
    { title: 'Subnet', dataIndex: 'subnet', key: 'subnet' },
    { title: 'Range Start', dataIndex: 'range_start', key: 'range_start' },
    { title: 'Range End', dataIndex: 'range_end', key: 'range_end' },
    {
      title: 'Actions',
      key: 'actions',
      width: 90,
      render: (_: unknown, record: IpPool) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="Delete this IP pool?" onConfirm={() => deleteMut.mutate(record.id)}>
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
          <GlobalOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          IP Address Management
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Add Pool
        </Button>
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

      <Modal
        title={editingPool ? 'Edit IP Pool' : 'Add IP Pool'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={createMut.isPending || updateMut.isPending}
      >
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="name" label="Pool Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="router_id" label="Router">
            <Select allowClear placeholder="Select router">
              {(routers || []).map((r) => (
                <Select.Option key={r.id} value={r.id}>
                  {r.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="subnet" label="Subnet (e.g. 192.168.10.0/24)" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="range_start" label="Range Start" rules={[{ required: true }]}>
            <Input placeholder="192.168.10.100" />
          </Form.Item>
          <Form.Item name="range_end" label="Range End" rules={[{ required: true }]}>
            <Input placeholder="192.168.10.200" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default IPAM;
