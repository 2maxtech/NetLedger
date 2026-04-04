import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Typography, Table, Button, Tag, Space, Statistic, Row, Col, message } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, AlertOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getSuricataStatus, getSuricataAlerts, getSuricataRules, reloadSuricata, startSuricata, stopSuricata } from '../../api/security';

const Suricata = () => {
  const queryClient = useQueryClient();
  const { data: status } = useQuery({ queryKey: ['suricata-status'], queryFn: () => getSuricataStatus().then((r) => r.data), refetchInterval: 10000 });
  const { data: alerts, isLoading: alertsLoading } = useQuery({ queryKey: ['suricata-alerts'], queryFn: () => getSuricataAlerts(100).then((r) => r.data) });
  const { data: rules } = useQuery({ queryKey: ['suricata-rules'], queryFn: () => getSuricataRules().then((r) => r.data) });

  const startMut = useMutation({ mutationFn: startSuricata, onSuccess: () => { message.success('Suricata started'); queryClient.invalidateQueries({ queryKey: ['suricata-status'] }); } });
  const stopMut = useMutation({ mutationFn: stopSuricata, onSuccess: () => { message.success('Suricata stopped'); queryClient.invalidateQueries({ queryKey: ['suricata-status'] }); } });
  const reloadMut = useMutation({ mutationFn: reloadSuricata, onSuccess: () => message.success('Rules reloaded') });

  const alertColumns = [
    { title: 'Time', key: 'time', render: (_: unknown, r: any) => dayjs(r.timestamp).format('HH:mm:ss'), width: 80 },
    { title: 'Severity', key: 'sev', render: (_: unknown, r: any) => {
      const s = r.alert?.severity;
      const colors: Record<number, string> = { 1: 'red', 2: 'orange', 3: 'blue' };
      return <Tag color={colors[s] || 'default'}>{s}</Tag>;
    }, width: 80 },
    { title: 'Signature', key: 'sig', render: (_: unknown, r: any) => r.alert?.signature || '-', ellipsis: true },
    { title: 'Source', key: 'src', render: (_: unknown, r: any) => `${r.src_ip || ''}:${r.src_port || ''}`, width: 160 },
    { title: 'Dest', key: 'dst', render: (_: unknown, r: any) => `${r.dest_ip || ''}:${r.dest_port || ''}`, width: 160 },
    { title: 'Protocol', dataIndex: 'proto', key: 'proto', width: 80 },
  ];

  const ruleColumns = [
    { title: 'File', dataIndex: 'name', key: 'name' },
    { title: 'Active Rules', dataIndex: 'active_rules', key: 'count' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}><AlertOutlined /> Suricata IDS/IPS</Typography.Title>
        <Space>
          {status?.active ? (
            <Button danger icon={<PauseCircleOutlined />} onClick={() => stopMut.mutate()} loading={stopMut.isPending}>Stop</Button>
          ) : (
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={() => startMut.mutate()} loading={startMut.isPending} style={{ background: '#10b981' }}>Start</Button>
          )}
          <Button icon={<ReloadOutlined />} onClick={() => reloadMut.mutate()} loading={reloadMut.isPending}>Reload Rules</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Status" valueRender={() => <Tag color={status?.active ? 'green' : 'red'}>{status?.active ? 'Running' : 'Stopped'}</Tag>} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Rule Files" value={rules?.length || 0} /></Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card><Statistic title="Recent Alerts" value={alerts?.length || 0} /></Card>
        </Col>
      </Row>

      <Card title="Recent Alerts" style={{ marginBottom: 16 }}>
        <Table columns={alertColumns} dataSource={alerts || []} loading={alertsLoading} rowKey={(r, i) => `${r.timestamp}-${i}`} size="small" pagination={{ pageSize: 20 }} />
      </Card>

      <Card title="Rule Files">
        <Table columns={ruleColumns} dataSource={rules || []} rowKey="name" size="small" pagination={false} />
      </Card>
    </div>
  );
};

export default Suricata;
