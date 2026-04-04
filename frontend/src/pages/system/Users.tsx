import { useState } from 'react';
import { Table, Card, Button, Modal, Form, Input, Select, Tag, Typography, Popconfirm, Space, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getUsers, createUser, updateUser, deleteUser, type StaffUser } from '../../api/users';
import { useAuth } from '../../hooks/useAuth';
import dayjs from 'dayjs';

const roleColors: Record<string, string> = { admin: '#e8700a', billing: '#f59e0b', technician: '#64748b' };

const Users = () => {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<StaffUser | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({ queryKey: ['users'], queryFn: getUsers });

  const createMut = useMutation({
    mutationFn: createUser,
    onSuccess: () => { message.success('User created'); closeModal(); queryClient.invalidateQueries({ queryKey: ['users'] }); },
    onError: () => message.error('Failed to create user'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) => updateUser(id, data),
    onSuccess: () => { message.success('User updated'); closeModal(); queryClient.invalidateQueries({ queryKey: ['users'] }); },
    onError: () => message.error('Failed to update user'),
  });

  const deleteMut = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => { message.success('User deactivated'); queryClient.invalidateQueries({ queryKey: ['users'] }); },
  });

  const closeModal = () => { setModalOpen(false); setEditingUser(null); form.resetFields(); };

  const openEdit = (user: StaffUser) => {
    setEditingUser(user);
    form.setFieldsValue({ username: user.username, email: user.email, role: user.role });
    setModalOpen(true);
  };

  const onFinish = (values: Record<string, unknown>) => {
    if (editingUser) updateMut.mutate({ id: editingUser.id, data: values });
    else createMut.mutate(values);
  };

  const columns = [
    { title: 'Username', dataIndex: 'username', key: 'username' },
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: 'Role', dataIndex: 'role', key: 'role', render: (role: string) => <Tag color={roleColors[role]}>{role}</Tag> },
    { title: 'Active', dataIndex: 'is_active', key: 'active', render: (v: boolean) => <Tag color={v ? '#10b981' : '#ef4444'}>{v ? 'Yes' : 'No'}</Tag> },
    { title: 'Created', dataIndex: 'created_at', key: 'created', render: (d: string) => dayjs(d).format('YYYY-MM-DD') },
    {
      title: 'Actions', key: 'actions',
      render: (_: unknown, record: StaffUser) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          {record.id !== currentUser?.id && (
            <Popconfirm title="Deactivate this user?" onConfirm={() => deleteMut.mutate(record.id)}>
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>Staff Users</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Add User</Button>
      </div>
      <Card>
        <Table dataSource={data?.data} columns={columns} rowKey="id" loading={isLoading} pagination={false} />
      </Card>
      <Modal title={editingUser ? 'Edit User' : 'Add User'} open={modalOpen} onCancel={closeModal} onOk={() => form.submit()} confirmLoading={createMut.isPending || updateMut.isPending}>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="Username" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}><Input /></Form.Item>
          {!editingUser && <Form.Item name="password" label="Password" rules={[{ required: true }]}><Input.Password /></Form.Item>}
          <Form.Item name="role" label="Role" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="admin">Admin</Select.Option>
              <Select.Option value="billing">Billing</Select.Option>
              <Select.Option value="technician">Technician</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Users;
