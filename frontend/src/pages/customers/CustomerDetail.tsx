import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Button, Space, Typography, Tabs, Popconfirm, message, Spin, Empty } from 'antd';
import { ArrowLeftOutlined, DisconnectOutlined, LinkOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getCustomer, disconnectCustomer, reconnectCustomer, throttleCustomer } from '../../api/customers';
import StatusTag from '../../components/StatusTag';
import dayjs from 'dayjs';

const CustomerDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => getCustomer(id!),
    enabled: !!id,
  });

  const customer = data?.data;

  const onActionSuccess = (action: string) => {
    message.success(`Customer ${action}`);
    queryClient.invalidateQueries({ queryKey: ['customer', id] });
  };

  const disconnectMut = useMutation({ mutationFn: () => disconnectCustomer(id!), onSuccess: () => onActionSuccess('disconnected') });
  const reconnectMut = useMutation({ mutationFn: () => reconnectCustomer(id!), onSuccess: () => onActionSuccess('reconnected') });
  const throttleMut = useMutation({ mutationFn: () => throttleCustomer(id!), onSuccess: () => onActionSuccess('throttled') });

  if (isLoading) return <Spin size="large" />;
  if (!customer) return <Empty description="Customer not found" />;

  const tabItems = [
    {
      key: 'overview',
      label: 'Overview',
      children: (
        <Descriptions column={2} bordered>
          <Descriptions.Item label="Full Name">{customer.full_name}</Descriptions.Item>
          <Descriptions.Item label="Status"><StatusTag status={customer.status} /></Descriptions.Item>
          <Descriptions.Item label="Email">{customer.email}</Descriptions.Item>
          <Descriptions.Item label="Phone">{customer.phone}</Descriptions.Item>
          <Descriptions.Item label="Address" span={2}>{customer.address || '-'}</Descriptions.Item>
          <Descriptions.Item label="PPPoE Username">{customer.pppoe_username}</Descriptions.Item>
          <Descriptions.Item label="PPPoE Password">••••••••</Descriptions.Item>
          <Descriptions.Item label="Plan">{customer.plan?.name || '-'}</Descriptions.Item>
          <Descriptions.Item label="Speed">{customer.plan ? `${customer.plan.download_mbps}/${customer.plan.upload_mbps} Mbps` : '-'}</Descriptions.Item>
          <Descriptions.Item label="Monthly Price">{customer.plan ? `₱${customer.plan.monthly_price}` : '-'}</Descriptions.Item>
          <Descriptions.Item label="Created">{dayjs(customer.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
        </Descriptions>
      ),
    },
    {
      key: 'sessions',
      label: 'Sessions',
      children: <Empty description="Session history will be available when the endpoint is implemented" />,
    },
    {
      key: 'activity',
      label: 'Activity',
      children: <Empty description="Activity log will be available when the endpoint is implemented" />,
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')}>Back</Button>
      </Space>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <Space>
            <Typography.Title level={4} style={{ margin: 0 }}>{customer.full_name}</Typography.Title>
            <StatusTag status={customer.status} />
            <Typography.Text type="secondary">{customer.plan?.name}</Typography.Text>
          </Space>
          <Space>
            {(customer.status === 'active') && (
              <>
                <Popconfirm title="Throttle this customer?" onConfirm={() => throttleMut.mutate()}>
                  <Button icon={<ThunderboltOutlined />} loading={throttleMut.isPending}>Throttle</Button>
                </Popconfirm>
                <Popconfirm title="Disconnect this customer?" onConfirm={() => disconnectMut.mutate()}>
                  <Button danger icon={<DisconnectOutlined />} loading={disconnectMut.isPending}>Disconnect</Button>
                </Popconfirm>
              </>
            )}
            {(customer.status === 'suspended') && (
              <>
                <Popconfirm title="Disconnect this customer?" onConfirm={() => disconnectMut.mutate()}>
                  <Button danger icon={<DisconnectOutlined />} loading={disconnectMut.isPending}>Disconnect</Button>
                </Popconfirm>
                <Popconfirm title="Reconnect this customer?" onConfirm={() => reconnectMut.mutate()}>
                  <Button type="primary" icon={<LinkOutlined />} loading={reconnectMut.isPending}>Reconnect</Button>
                </Popconfirm>
              </>
            )}
            {(customer.status === 'disconnected') && (
              <Popconfirm title="Reconnect this customer?" onConfirm={() => reconnectMut.mutate()}>
                <Button type="primary" icon={<LinkOutlined />} loading={reconnectMut.isPending}>Reconnect</Button>
              </Popconfirm>
            )}
          </Space>
        </div>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
};

export default CustomerDetail;
