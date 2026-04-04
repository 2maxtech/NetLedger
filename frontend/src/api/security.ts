import client from './client';

// Suricata
export const getSuricataStatus = () => client.get('/security/suricata/status');
export const getSuricataStats = () => client.get('/security/suricata/stats');
export const getSuricataAlerts = (limit?: number) => client.get('/security/suricata/alerts', { params: { limit: limit || 50 } });
export const getSuricataRules = () => client.get('/security/suricata/rules');
export const reloadSuricata = () => client.post('/security/suricata/reload');
export const startSuricata = () => client.post('/security/suricata/start');
export const stopSuricata = () => client.post('/security/suricata/stop');

// DNS Filtering
export const getBlockedDomains = () => client.get<string[]>('/security/dns-filter/domains');
export const addBlockedDomain = (domain: string) => client.post('/security/dns-filter/domain', { domain });
export const removeBlockedDomain = (domain: string) => client.delete('/security/dns-filter/domain', { data: { domain } });
export const applyDnsBlocklist = (domains: string[]) => client.post('/security/dns-filter/apply', { domains });

// GeoIP
export const getBlockedCountries = () => client.get<string[]>('/security/geoip/countries');
export const applyGeoipBlock = (countryCodes: string[]) => client.post('/security/geoip/apply', { country_codes: countryCodes });
