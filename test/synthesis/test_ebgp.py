import unittest

import z3
from synet.utils.common import PathReq
from synet.utils.common import PathProtocols
from synet.topo.graph import NetworkGraph
from synet.topo.bgp import Access
from synet.topo.bgp import ActionSetCommunity
from synet.topo.bgp import ActionSetLocalPref
from synet.topo.bgp import Announcement
from synet.topo.bgp import BGP_ATTRS_ORIGIN
from synet.topo.bgp import Community
from synet.topo.bgp import CommunityList
from synet.topo.bgp import IpPrefixList
from synet.topo.bgp import MatchCommunitiesList
from synet.topo.bgp import MatchIpPrefixListList
from synet.topo.bgp import MatchNextHop
from synet.topo.bgp import RouteMap
from synet.topo.bgp import RouteMapLine

from synet.utils.policy import OrOp
from synet.utils.policy import SMTActions
from synet.utils.policy import SMTCommunity
from synet.utils.policy import SMTCommunityList
from synet.utils.policy import SMTLocalPref
from synet.utils.policy import SMTIpPrefix
from synet.utils.policy import SMTIpPrefixList
from synet.utils.policy import SMTMatch
from synet.utils.policy import SMTMatches
from synet.utils.policy import SMTNextHop
from synet.utils.policy import SMTRouteMap
from synet.utils.policy import SMTRouteMapLine
from synet.utils.policy import SMTSetCommunity
from synet.utils.policy import SMTSetLocalPref

from synet.utils.smt_context import SMTASPathWrapper
from synet.utils.smt_context import SMTASPathLenWrapper
from synet.utils.smt_context import SMTContext
from synet.utils.smt_context import SMTCommunityWrapper
from synet.utils.smt_context import SMTLocalPrefWrapper
from synet.utils.smt_context import SMTNexthopWrapper
from synet.utils.smt_context import SMTOriginWrapper
from synet.utils.smt_context import SMTPeerWrapper
from synet.utils.smt_context import SMTPrefixWrapper
from synet.utils.smt_context import SMTPermittedWrapper
from synet.utils.smt_context import get_as_path_key
from synet.utils.smt_context import is_empty
from synet.utils.smt_context import VALUENOTSET


from synet.synthesis.propagation import EBGPPropagation

class SMTSetup(unittest.TestCase):
    def _pre_load(self):
        # Communities
        c1 = Community("100:16")
        c2 = Community("100:17")
        c3 = Community("100:18")
        self.all_communities = (c1, c2, c3)

        ann1 = Announcement(
            prefix='Google', peer='ATT', origin=BGP_ATTRS_ORIGIN.EBGP,
            as_path=[1, 2, 5, 7, 6], as_path_len=5,
            next_hop='ATTHop', local_pref=100,
            communities={c1: False, c2: False, c3: False}, permitted=True)

        ann2 = Announcement(
            prefix='Google', peer='DT', origin=BGP_ATTRS_ORIGIN.EBGP,
            as_path=[3, 2, 5, 7, 6], as_path_len=5,
            next_hop='DTHop', local_pref=100,
            communities={c1: False, c2: False, c3: False}, permitted=True)

        ann3 = Announcement(
            prefix='YouTube', peer='ATT', origin=BGP_ATTRS_ORIGIN.EBGP,
            as_path=[1, 2, 5, 7, 8], as_path_len=5,
            next_hop='ATTHop', local_pref=100,
            communities={c1: True, c2: False, c3: True}, permitted=True)

        self.anns = {
            'ATT_Google': ann1,
            'DT_Google': ann2,
            'ATT_YouTube': ann3,
        }

    def _define_types(self, prefix_list=None, next_hope_list=None,
                      peer_list=None, as_path_list=None):
        # Ann Type
        (self.ann_sort, self.announcements) = \
            z3.EnumSort('AnnouncementSort', self.anns.keys())

        ann_map = dict([(str(ann), ann) for ann in self.announcements])
        self.ann_map = ann_map
        self.ann_var_map = dict([(self.ann_map[ann], self.anns[str(ann)]) for ann in self.ann_map])

        self.local_pref_fun = z3.Function('LocalPref', self.ann_sort, z3.IntSort())
        self.permitted_fun = z3.Function('PermittedFun', self.ann_sort, z3.BoolSort())

        if not prefix_list:
            l = [ann.prefix for ann in self.anns.values() if not is_empty(ann.prefix)]
            prefix_list = list(set(l))
        (self.prefix_sort, self.prefixes) = z3.EnumSort('PrefixSort', prefix_list)

        prefix_map = dict([(str(prefix), prefix) for prefix in self.prefixes])
        self.prefix_map = prefix_map
        self.prefix_fun = z3.Function('PrefixFunc', self.ann_sort, self.prefix_sort)

        if not peer_list:
            l = [x.peer for x in self.anns.values() if not is_empty(x.peer)]
            peer_list = list(set(l))
        (self.peer_sort, self.peers) = z3.EnumSort('PeerSort', peer_list)
        peer_map = dict([(str(p), p) for p in self.peers])
        self.peer_map = peer_map
        self.peer_fun = z3.Function('PeerFun', self.ann_sort, self.peer_sort)

        origin_list = BGP_ATTRS_ORIGIN.__members__.keys()
        (self.origin_sort, self.origins) = z3.EnumSort('OriginSort', origin_list)
        origin_map = dict([(str(p), p) for p in self.origins])
        for k, v in BGP_ATTRS_ORIGIN.__members__.iteritems():
            origin_map[v] = origin_map[k]
        self.origin_map = origin_map
        self.origin_fun = z3.Function('OriginFun', self.ann_sort, self.origin_sort)

        if not as_path_list:
            l = [get_as_path_key(x.as_path) for x in self.anns.values()
                 if not is_empty(x.as_path)]
            as_path_list = list(set(l))
        (self.as_path_sort, self.as_paths) = z3.EnumSort('PrefixSort', as_path_list)

        as_path_map = dict([(str(p), p) for p in self.as_paths])
        self.as_path_map = as_path_map
        self.as_path_fun = z3.Function('AsPathFunc', self.ann_sort, self.as_path_sort)
        self.as_path_len_fun = z3.Function('AsPathLenFunc', self.ann_sort, z3.IntSort())

        if not next_hope_list:
            l = [x.next_hop for x in self.anns.values() if not is_empty(x.next_hop)]
            next_hope_list = list(set(l))
        (self.next_hop_sort, self.next_hops) = z3.EnumSort('NexthopSort', next_hope_list)

        next_hop_map = dict([(str(p), p) for p in self.next_hops])
        self.next_hop_map = next_hop_map
        self.next_hop_fun = z3.Function('NexthopFunc', self.ann_sort, self.next_hop_sort)

        # Create functions for communities
        self.communities_fun = {}
        self.reverse_communities = {}
        for c in self.all_communities:
            name = 'Has_%s' % c.name
            self.communities_fun[c] = z3.Function(name, self.ann_sort, z3.BoolSort())
            self.reverse_communities[name] = c

        self.route_denied_fun = z3.Function('route_denied', self.ann_sort, z3.BoolSort())

    def setUp(self):
        self._pre_load()
        self._define_types()

    def get_solver(self):
        return z3.Solver()

    def get_context(self):
        # Create wrapper
        wprefix = SMTPrefixWrapper(
            'prefixw', self.ann_sort, self.ann_var_map,
            self.prefix_fun, self.prefix_sort, self.prefix_map)

        wpeer = SMTPeerWrapper(
            'wpeer', self.ann_sort, self.ann_var_map,
            self.peer_fun, self.peer_sort, self.peer_map)

        worigin = SMTOriginWrapper(
            'worigin', self.ann_sort, self.ann_var_map,
            self.origin_fun, self.origin_sort, self.origin_map)

        waspath = SMTASPathWrapper(
            'waspath', self.ann_sort, self.ann_var_map,
            self.as_path_fun, self.as_path_sort, self.as_path_map)

        waspathlen = SMTASPathLenWrapper(
            'waspathlen', self.ann_sort, self.ann_var_map,
            self.as_path_len_fun)

        wnext_hop = SMTNexthopWrapper(
            'wnext_hop', self.ann_sort, self.ann_var_map,
            self.next_hop_fun, self.next_hop_sort, self.next_hop_map)

        wlocalpref = SMTLocalPrefWrapper(
            'wlocalpref', self.ann_sort, self.ann_var_map,
            self.local_pref_fun)

        wpermitted = SMTPermittedWrapper(
            'wpermitted', self.ann_sort, self.ann_var_map,
            self.permitted_fun)

        wcommunities = {}
        for community in self.all_communities:
            name = community.name
            wc1 = SMTCommunityWrapper(
                'w%s' % name, community, self.ann_sort,
                self.ann_var_map, self.communities_fun[community])
            wcommunities[community] = wc1

        ctx = SMTContext('ctx1', self.anns, self.ann_map, self.ann_sort,
                         wprefix, wpeer, worigin, waspath, waspathlen,
                         wnext_hop, wlocalpref, wcommunities, wpermitted)
        return ctx


class EBGPTest(SMTSetup):
    def get_g(self):
        """
        Get a simple graph of 1 local router and two peers ATT, DT
        :return: Networkx Digraph
        """
        # Start with some initial inputs
        # This input only define routers
        g_phy = NetworkGraph()
        g_phy.add_router('R1')
        g_phy.add_peer('ATT')
        g_phy.add_peer('DT')
        g_phy.set_bgp_asnum('R1', 100)
        g_phy.set_bgp_asnum('ATT', 2000)
        g_phy.set_bgp_asnum('DT', 3000)

        g_phy.add_peer_edge('ATT', 'R1')
        g_phy.add_peer_edge('R1', 'ATT')
        g_phy.add_peer_edge('DT', 'R1')
        g_phy.add_peer_edge('R1', 'DT')

        g_phy.add_bgp_neighbor('R1', 'ATT')
        g_phy.add_bgp_neighbor('R1', 'DT')

        g_phy.add_bgp_advertise('ATT', self.anns['ATT_Google'])
        g_phy.add_bgp_advertise('ATT', self.anns['ATT_YouTube'])
        g_phy.add_bgp_advertise('DT', self.anns['DT_Google'])

        return g_phy


    def setUp(self):
        super(EBGPTest, self).setUp()

    def load_import_route_maps(self, g, node, neighbor, value):
        set_localpref = ActionSetLocalPref(value)
        line = RouteMapLine(matches=None, actions=[set_localpref],
                            access=Access.permit, lineno=10)
        name = "From_%s_%s" % (node, neighbor)
        rmap = RouteMap(name=name, lines=[line])
        g.add_route_map(node, rmap)
        g.add_bgp_imoprt_route_map(node, neighbor, rmap.name)

    def test_small(self):
        g = self.get_g()

        youtube_req1 = PathReq(PathProtocols.BGP, 'YouTube', ['ATT', 'R1'], 10)
        google_req1 = PathReq(PathProtocols.BGP, 'Google', ['DT', 'R1'], 10)

        reqs = [
            youtube_req1,
            google_req1,
        ]
        self.load_import_route_maps(g, 'R1', 'ATT', 100)
        self.load_import_route_maps(g, 'R1', 'DT', VALUENOTSET)
        p = EBGPPropagation(reqs, g)
        r1 = p.network_graph.node['R1']['syn']['box']
        p.synthesize()

        solver = z3.Solver()
        p.add_constraints(solver)
        ret = solver.check()
        print solver.unsat_core()
        self.assertEquals(ret, z3.sat)
        p.set_model(solver.model())
        print r1.get_config()