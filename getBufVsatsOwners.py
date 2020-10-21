
import os, sys, time, collections, re, telnetlib


class CliParser():

    @staticmethod
    def parse_bb_links(bb_links_output):
        vsat_ids = []
        for line in bb_links_output.split('\n\r'):
            if re.match('^\|\W(\d*)\W\|', line):
                bb_link = re.match('^\|\W(\d*)\W\|', line)
                vsat_ids.append(bb_link.group(1))
        return (vsat_ids)                                                


    @staticmethod
    def parse_buf_own(raw_data, vsat_id):
        parsed_output = collections.OrderedDict()
        parsed_output['entry_id'] = vsat_id
        match_found = False
        for line in raw_data.split('\n\r'):
            #print(line)
            if re.match(r'\W'+vsat_id+r'\W*(\d*)\W*(\d*)', line):
                match_found = True
                parsed_output['Outbound_buf']=re.match(r'\W'+vsat_id+r'\W*(\d*)\W*\d*', line).group(1)
                parsed_output['Inbound_buf']=re.match(r'\W'+vsat_id+r'\W*\d*\W*(\d*)', line).group(1)
        if not match_found:
            parsed_output['Outbound_buf']='0'
            parsed_output['Inbound_buf']='0'
        return (parsed_output)

    def __init__(self, parse_map=''):                           
        self.parse_map = parse_map
        self.aggregated_csv = {'headline':'', 'data':''}


    def parse_output(self, raw_output, entry_id='', greedy = False): 
        parsed_output = collections.OrderedDict()
        parsed_output['entry_id'] = entry_id
        for line in raw_output.split('\n\r'):
            print("$"+line+"$")
            for regexp in self.parse_map:
                if self.parse_map[regexp].search(line):
                    parsed_value = self.parse_map[regexp].search(line)
                    parsed_output[regexp] = parsed_value.group(1)
                    if not greedy: break
        return (parsed_output)

    def aggregate_csv(self, parsed_output, datetime=''):
        if not datetime: 
            datetime = time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())
        headline = 'datetime,'+','.join(i for i in parsed_output)+'\n'
        csvline = datetime + ',' + ','.join(parsed_output[i] for i in parsed_output)+'\n'
        if not self.aggregated_csv['headline']:
            self.aggregated_csv['headline'] = headline
        self.aggregated_csv['data'] += csvline
        return (self.aggregated_csv)

    def write_csv_file(self, filename, headline=False, data=True, clear_aggregated_csv_in_mem = True):
        with open(filename, 'a+') as file:
            if (headline or os.stat(filename).st_size == 0): file.write(self.aggregated_csv['headline'])
            if data: file.write(self.aggregated_csv['data'])
        if clear_aggregated_csv_in_mem:
            self.aggregated_csv = {'headline':'', 'data':''}

class TelnetCli():

    def __init__(self, host):
        self.HOST = host
        self.WAIT_TIMEOUT = 0.2
        self.conn = telnetlib.Telnet(self.HOST)

    def send_command(self, command, timeout=0.01, by_symbol=False):
        command += "\r\n"    
        if by_symbol:
            for character in command:
                self.conn.write(character.encode('ascii'))
                time.sleep(timeout)
        else:
            self.conn.write(command.encode('ascii'))
            
        time.sleep(self.WAIT_TIMEOUT)
        return True

    def read_output(self):
        return self.conn.read_very_eager()

class ParsHelper():

    @staticmethod
    def get_elemets_ip():
        return {"DPS" : '172.17.%s4.1' % ParsHelper.get_domain(), "HSP" : '172.17.%s2.1' % ParsHelper.get_domain()}

    @staticmethod
    def get_domain():
        possible_cfg_files = ["ifcfg-bond0.17", "ifcfg-br17", "ifcfg-eth0"]
        for cfg_file in possible_cfg_files:
            possible_cfg_path = "/etc/sysconfig/network-scripts/"+cfg_file
            if os.path.isfile(possible_cfg_path):
                cfg_path = possible_cfg_path
                break
        
        with open(cfg_path,'r') as file:
            domain_id = re.search('.*IPADDR=\d*\.\d*\.(\d*).*',file.read()).group(1)[1]

        return domain_id

class ParsingMap():

    @staticmethod
    def pars_compiler(pars_dict):
        parsingMap = {}
        for field in pars_dict:
            parsingMap[field] = re.compile(pars_dict[field])
        return parsingMap

    @staticmethod
    def hsp_stat_cac_link():
        parsingMap = {}
        types = ['new','modify','change_to_rob','change_to_eff']

        pars_dict = {'new':r'\W*Number.*new.*-\W\b@\b\W*(\d*)',
                        'modify':r'\W*Number.*modify.*-\W\b@\b\W*(\d*)',
                        'change_to_rob':r'\W*Number.*change.*robust.*-\W\b@\b\W*(\d*)',
                        'change_to_eff':r'\W*Number.*change.*efficient.*-\W\b@\b\W*(\d*)'}
        fields = ['NO_CAUSE', 'BACKHAULING_LIMIT', 'CBR_LIMIT', 'NO_FREE_BW', 
                  'NO_VOIP_ALLOC_OPTION', 'GLOBAL_BW_LIMIT', 'MPN_MIR', 'OUT_OF_VSAT_CAPACITY', 'NO_FREE_BW_FOR_VOIP']

        for tip in types:
                for filed in fields:
                        parsingMap[tip+'_'+filed] = re.compile(pars_dict[tip].replace('@',filed))
        return parsingMap

    @staticmethod
    def hsp_tele_cac_global():
        
        pars_dict = {'Current SDR':r'\W*Current SDR capacity usage:\W*(\d*)%',
                    'Max SDR':r'.*Max SDR Capacity Limit:\W*(\d*)%'}
        return ParsingMap.pars_compiler(pars_dict)

    @staticmethod
    def buf_vsats_owners():        
        pars_dict = {'Outbound_buffers':r'\W1352\W*(\d*)\W*\d*',
                    'Inbound_buffers':r'\W1352\W*\d*\W*(\d*)',
                    'Outbound_buffers':r'\W1652\W*(\d*)\W*\d*',
                    'Inbound_buffers':r'\W1462\W*\d*\W*(\d*)'}
        return ParsingMap.pars_compiler(pars_dict)


bblinks = ["1282","1288","1384","1289","1383"]
def main():

    #SCRIPT INITIAL PARAMETERS
    DPS = ParsHelper.get_elemets_ip()["DPS"]   # or specify manually ex: DPS = '172.17.14.1'
    FILENAME = 'test.csv'
    SPECIAL_OPT = False
    DATETIME = time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())

    if len(sys.argv) > 1: 
        if sys.argv[1] == "-s":
            SPECIAL_OPT = True
            if len(sys.argv) > 2: FILENAME = str(sys.argv[2])+'.csv'
        else: FILENAME = str(sys.argv[1])+'.csv'

    
    #SCRIPT LOGIC
    #Here parsing object is creating supplying parsing map as argument
    dps_telnet = TelnetCli(DPS)
    pars_worker = CliParser()

    #Gathering list of VSAT IDs
    print ('\nGathering list of VSAT IDs')
    dps_telnet.send_command('bb links')
    bb_links = dps_telnet.read_output()
    vsat_ids = CliParser.parse_bb_links(bb_links)
    print ('Got '+str(len(vsat_ids))+' VSATs')

    dps_telnet.send_command('sym set buf_vsat_owners_in_progress 0 4')
    time.sleep(2)
    dps_telnet.send_command('buf vsat_owners')
    buff_out = dps_telnet.read_output()

    for vsat_id in vsat_ids:
        raw_output = CliParser.parse_buf_own(buff_out, vsat_id)
        pars_worker.aggregate_csv(raw_output, datetime = DATETIME)
    print("Writing to file")
    pars_worker.write_csv_file(FILENAME)


if __name__ == "__main__":
    main()
