import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Typography, Table, Button, Input, message, Space, Tag, Popconfirm, Tabs, Select } from 'antd';
import { PlusOutlined, DeleteOutlined, ReloadOutlined, StopOutlined, GlobalOutlined } from '@ant-design/icons';
import { getBlockedDomains, addBlockedDomain, removeBlockedDomain, getBlockedCountries, applyGeoipBlock } from '../../api/security';

const COUNTRIES = [
  { code: 'CN', name: 'China' }, { code: 'RU', name: 'Russia' }, { code: 'KP', name: 'North Korea' },
  { code: 'IR', name: 'Iran' }, { code: 'IN', name: 'India' }, { code: 'BR', name: 'Brazil' },
  { code: 'NG', name: 'Nigeria' }, { code: 'VN', name: 'Vietnam' }, { code: 'PK', name: 'Pakistan' },
  { code: 'BD', name: 'Bangladesh' }, { code: 'ID', name: 'Indonesia' }, { code: 'UA', name: 'Ukraine' },
];

const ContentFilter = () => {
  const queryClient = useQueryClient();
  const [newDomain, setNewDomain] = useState('');
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);

  const { data: domains, isLoading: domainsLoading } = useQuery({ queryKey: ['blocked-domains'], queryFn: () => getBlockedDomains().then((r) => r.data) });
  const { data: countries } = useQuery({
    queryKey: ['blocked-countries'],
    queryFn: () => getBlockedCountries().then((r) => r.data),
    onSuccess: (data: string[]) => setSelectedCountries(data),
  });

  const addDomainMut = useMutation({
    mutationFn: addBlockedDomain,
    onSuccess: () => { message.success('Domain blocked'); setNewDomain(''); queryClient.invalidateQueries({ queryKey: ['blocked-domains'] }); },
    onError: () => message.error('Failed to block domain'),
  });

  const removeDomainMut = useMutation({
    mutationFn: removeBlockedDomain,
    onSuccess: () => { message.success('Domain unblocked'); queryClient.invalidateQueries({ queryKey: ['blocked-domains'] }); },
  });

  const geoipMut = useMutation({
    mutationFn: applyGeoipBlock,
    onSuccess: () => { message.success('GeoIP rules applied'); queryClient.invalidateQueries({ queryKey: ['blocked-countries'] }); },
    onError: () => message.error('Failed to apply GeoIP rules'),
  });

  const domainColumns = [
    { title: 'Domain', dataIndex: 'domain', key: 'domain', render: (_: unknown, __: unknown, i: number) => domains?.[i] || '' },
    {
      title: '', key: 'actions', width: 60,
      render: (_: unknown, __: unknown, i: number) => (
        <Popconfirm title="Unblock?" onConfirm={() => removeDomainMut.mutate(domains?.[i] || '')}>
          <Button type="link" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const items = [
    {
      key: 'dns',
      label: 'DNS Filtering',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Input placeholder="example.com" value={newDomain} onChange={(e) => setNewDomain(e.target.value)} onPressEnter={() => newDomain && addDomainMut.mutate(newDomain)} style={{ width: 300 }} />
            <Button type="primary" icon={<StopOutlined />} onClick={() => newDomain && addDomainMut.mutate(newDomain)} loading={addDomainMut.isPending}>Block Domain</Button>
          </Space>
          <Table
            columns={domainColumns}
            dataSource={(domains || []).map((d: string, i: number) => ({ key: i, domain: d }))}
            loading={domainsLoading}
            rowKey="key"
            size="small"
            pagination={{ pageSize: 20 }}
          />
        </div>
      ),
    },
    {
      key: 'geoip',
      label: 'GeoIP Blocking',
      children: (
        <div>
          <Typography.Paragraph type="secondary">Block traffic from selected countries. Requires nftables GeoIP module on the gateway.</Typography.Paragraph>
          <Select
            mode="multiple"
            style={{ width: '100%', marginBottom: 16 }}
            placeholder="Select countries to block"
            value={selectedCountries}
            onChange={setSelectedCountries}
            options={COUNTRIES.map((c) => ({ value: c.code, label: `${c.name} (${c.code})` }))}
          />
          <Button type="primary" danger icon={<GlobalOutlined />} onClick={() => geoipMut.mutate(selectedCountries)} loading={geoipMut.isPending}>
            Apply GeoIP Rules ({selectedCountries.length} countries)
          </Button>
          {countries && countries.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Typography.Text strong>Currently Blocked:</Typography.Text>
              <div style={{ marginTop: 8 }}>{countries.map((c: string) => <Tag key={c} color="red">{c}</Tag>)}</div>
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}><StopOutlined /> Content Filtering</Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={() => { queryClient.invalidateQueries({ queryKey: ['blocked-domains'] }); queryClient.invalidateQueries({ queryKey: ['blocked-countries'] }); }} />
      </div>
      <Card><Tabs items={items} /></Card>
    </div>
  );
};

export default ContentFilter;
