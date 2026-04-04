import { useState } from 'react';
import {
  Table, Card, Select, DatePicker, Space, Typography,
} from 'antd';
import { AuditOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import dayjs from 'dayjs';
import client from '../api/client';

interface AuditLog {
  id: string;
  user: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  ip_address: string | null;
  created_at: string;
}

const ENTITY_TYPES = [
  'customer', 'invoice', 'payment', 'plan', 'router',
  'ticket', 'voucher', 'user', 'expense',
];

const AuditLogs = () => {
  const [entityType, setEntityType] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [page, setPage] = useState(1);

  const params: Record<string, any> = { page, size: 50 };
  if (entityType) params.entity_type = entityType;
  if (dateRange?.[0]) params.from_date = dateRange[0].format('YYYY-MM-DD');
  if (dateRange?.[1]) params.to_date = dateRange[1].format('YYYY-MM-DD');

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, entityType, dateRange],
    queryFn: () => client.get('/audit-logs/', { params }).then((r) => r.data),
  });

  const logs: AuditLog[] = Array.isArray(data) ? data : (data?.items || []);
  const total: number = data?.total || logs.length;

  const columns = [
    {
      title: 'Timestamp',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm:ss'),
      width: 170,
    },
    {
      title: 'User',
      dataIndex: 'user',
      key: 'user',
      render: (v: string | null) => v || '-',
      width: 130,
    },
    { title: 'Action', dataIndex: 'action', key: 'action', ellipsis: true },
    {
      title: 'Entity Type',
      dataIndex: 'entity_type',
      key: 'entity_type',
      width: 120,
    },
    {
      title: 'Entity ID',
      dataIndex: 'entity_id',
      key: 'entity_id',
      render: (v: string | null) => v ? v.slice(0, 8) + '...' : '-',
      width: 100,
    },
    {
      title: 'IP Address',
      dataIndex: 'ip_address',
      key: 'ip_address',
      render: (v: string | null) => v || '-',
      width: 130,
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <AuditOutlined style={{ color: '#e8700a', marginRight: 8 }} />
          Audit Logs
        </Typography.Title>
      </div>
      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="Entity type"
            allowClear
            style={{ width: 160 }}
            value={entityType}
            onChange={(v) => { setEntityType(v); setPage(1); }}
          >
            {ENTITY_TYPES.map((t) => (
              <Select.Option key={t} value={t}>
                {t}
              </Select.Option>
            ))}
          </Select>
          <DatePicker.RangePicker
            onChange={(dates) => {
              setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null);
              setPage(1);
            }}
          />
        </Space>
        <Table
          dataSource={logs}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          size="small"
          pagination={{
            current: page,
            pageSize: 50,
            total,
            onChange: setPage,
            showTotal: (t) => `${t} entries`,
          }}
        />
      </Card>
    </div>
  );
};

export default AuditLogs;
