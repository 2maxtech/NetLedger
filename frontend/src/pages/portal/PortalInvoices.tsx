import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Typography, Table, Button, message, Space } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined, WifiOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import dayjs from 'dayjs';
import StatusTag from '../../components/StatusTag';
import { getPortalInvoices, downloadPortalInvoicePdf } from '../../api/portal';
import type { PortalInvoice } from '../../api/portal';

const PortalInvoices = () => {
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ['portal-invoices', page],
    queryFn: () => getPortalInvoices({ page, size: 20 }).then((r) => r.data),
  });

  const columns = [
    { title: 'Plan', dataIndex: 'plan_name', key: 'plan' },
    { title: 'Amount', key: 'amount', render: (_: unknown, r: PortalInvoice) => `₱${Number(r.amount).toFixed(2)}` },
    { title: 'Paid', key: 'paid', render: (_: unknown, r: PortalInvoice) => `₱${Number(r.total_paid).toFixed(2)}` },
    { title: 'Due Date', dataIndex: 'due_date', key: 'due' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (s: string) => <StatusTag status={s} /> },
    { title: 'Issued', dataIndex: 'issued_at', key: 'issued', render: (d: string) => dayjs(d).format('YYYY-MM-DD') },
    {
      title: '',
      key: 'actions',
      width: 80,
      render: (_: unknown, r: PortalInvoice) => (
        <Button
          type="link"
          size="small"
          icon={<DownloadOutlined />}
          onClick={async () => {
            try {
              const res = await downloadPortalInvoicePdf(r.id);
              const url = window.URL.createObjectURL(new Blob([res.data]));
              const link = document.createElement('a');
              link.href = url;
              link.download = `invoice-${r.id.slice(0, 8)}.pdf`;
              link.click();
              window.URL.revokeObjectURL(url);
            } catch { message.error('Failed to download PDF'); }
          }}
        >
          PDF
        </Button>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Link to="/portal"><ArrowLeftOutlined /> Back to Dashboard</Link>
      </Space>
      <Typography.Title level={4}><WifiOutlined style={{ color: '#e8700a' }} /> My Invoices</Typography.Title>
      <Card>
        <Table
          columns={columns}
          dataSource={data?.items || []}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: page,
            pageSize: 20,
            total: data?.total || 0,
            onChange: setPage,
          }}
        />
      </Card>
    </div>
  );
};

export default PortalInvoices;
