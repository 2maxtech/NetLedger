import { useState } from 'react';
import { Table, Card, Select, Tabs, Typography, Space, Tag } from 'antd';
import { FireOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { getRouters } from '../api/routers';
import client from '../api/client';

const Hotspot = () => {
  const [routerId, setRouterId] = useState<string | undefined>();

  const { data: routers } = useQuery({
    queryKey: ['routers'],
    queryFn: () => getRouters().then((r) => r.data),
  });

  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ['hotspot-users', routerId],
    queryFn: () =>
      client
        .get('/network/hotspot/users', { params: { router_id: routerId } })
        .then((r) => r.data),
    enabled: !!routerId,
  });

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['hotspot-sessions', routerId],
    queryFn: () =>
      client
        .get('/network/hotspot/sessions', { params: { router_id: routerId } })
        .then((r) => r.data),
    enabled: !!routerId,
  });

  const userColumns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Profile', dataIndex: 'profile', key: 'profile' },
    { title: 'Password', dataIndex: 'password', key: 'password' },
    {
      title: 'Disabled',
      dataIndex: 'disabled',
      key: 'disabled',
      render: (v: boolean) => (
        <Tag color={v ? '#ef4444' : '#10b981'}>{v ? 'Yes' : 'No'}</Tag>
      ),
    },
    { title: 'Uptime Limit', dataIndex: 'limit-uptime', key: 'uptime_limit', render: (v: any) => v || '-' },
    { title: 'Bytes In', dataIndex: 'bytes-in', key: 'bytes_in', render: (v: any) => v || '-' },
  ];

  const sessionColumns = [
    { title: 'User', dataIndex: 'user', key: 'user' },
    { title: 'IP Address', dataIndex: 'address', key: 'address' },
    { title: 'MAC', dataIndex: 'mac-address', key: 'mac' },
    { title: 'Uptime', dataIndex: 'uptime', key: 'uptime' },
    { title: 'Bytes In', dataIndex: 'bytes-in', key: 'bytes_in' },
    { title: 'Bytes Out', dataIndex: 'bytes-out', key: 'bytes_out' },
  ];

  const users: any[] = Array.isArray(usersData) ? usersData : (usersData?.users || []);
  const sessions: any[] = Array.isArray(sessionsData) ? sessionsData : (sessionsData?.sessions || []);

  const tabItems = [
    {
      key: 'users',
      label: 'Users',
      children: (
        <Table
          dataSource={users}
          columns={userColumns}
          rowKey="name"
          loading={usersLoading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      ),
    },
    {
      key: 'sessions',
      label: 'Active Sessions',
      children: (
        <Table
          dataSource={sessions}
          columns={sessionColumns}
          rowKey=".id"
          loading={sessionsLoading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <FireOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Hotspot
        </Typography.Title>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Typography.Text strong>Router:</Typography.Text>
          <Select
            placeholder="Select router"
            style={{ width: 220 }}
            value={routerId}
            onChange={setRouterId}
          >
            {(routers || []).map((r) => (
              <Select.Option key={r.id} value={r.id}>
                {r.name}
              </Select.Option>
            ))}
          </Select>
        </Space>

        {routerId ? (
          <Tabs items={tabItems} />
        ) : (
          <Typography.Text type="secondary">
            Please select a router to view hotspot data.
          </Typography.Text>
        )}
      </Card>
    </div>
  );
};

export default Hotspot;
