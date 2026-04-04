import { useState } from 'react';
import {
  Table, Card, Button, Modal, Form, Input, Select, Typography, Popconfirm, Space, message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, EnvironmentOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAreas, createArea, updateArea, deleteArea, getRouters,
  type AreaType,
} from '../api/routers';

const Areas = () => {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingArea, setEditingArea] = useState<AreaType | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['areas'],
    queryFn: () => getAreas().then((r) => r.data),
  });

  const { data: routers } = useQuery({
    queryKey: ['routers'],
    queryFn: () => getRouters().then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: createArea,
    onSuccess: () => {
      message.success('Area created');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['areas'] });
    },
    onError: () => message.error('Failed to create area'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateArea(id, data),
    onSuccess: () => {
      message.success('Area updated');
      closeModal();
      queryClient.invalidateQueries({ queryKey: ['areas'] });
    },
    onError: () => message.error('Failed to update area'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteArea,
    onSuccess: () => {
      message.success('Area deleted');
      queryClient.invalidateQueries({ queryKey: ['areas'] });
    },
    onError: () => message.error('Failed to delete area'),
  });

  const closeModal = () => {
    setModalOpen(false);
    setEditingArea(null);
    form.resetFields();
  };

  const openEdit = (area: AreaType) => {
    setEditingArea(area);
    form.setFieldsValue({
      name: area.name,
      description: area.description,
      router_id: area.router_id,
    });
    setModalOpen(true);
  };

  const onFinish = (values: any) => {
    if (editingArea) updateMut.mutate({ id: editingArea.id, data: values });
    else createMut.mutate(values);
  };

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Router',
      key: 'router',
      render: (_: unknown, r: AreaType) => r.router?.name || '-',
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: AreaType) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm title="Delete this area?" onConfirm={() => deleteMut.mutate(record.id)}>
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
          <EnvironmentOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Areas
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          Add Area
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
        title={editingArea ? 'Edit Area' : 'Add Area'}
        open={modalOpen}
        onCancel={closeModal}
        onOk={() => form.submit()}
        confirmLoading={createMut.isPending || updateMut.isPending}
      >
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} />
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
        </Form>
      </Modal>
    </div>
  );
};

export default Areas;
