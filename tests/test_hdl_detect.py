import pytest

from odatix.lib import hdl_detect as h


def _verilog(text, path="top.sv"):
    return h._verilog_units(h._strip_verilog(text), path)


def _vhdl(text, path="top.vhd"):
    return h._vhdl_units(h._strip_vhdl(text), path)


def _ports(*names):
    """A module whose 1-bit inputs are `names`, no logic: the names alone decide."""
    return _verilog("module m(input " + ", input ".join(names) + ", output [7:0] q); endmodule")[0]


def _clock(unit, units=()):
    return [c.value for c in h.clock_candidates(unit, units)]


def _reset(unit, units=()):
    return [c.value for c in h.reset_candidates(unit, units)]


@pytest.mark.parametrize("name", [
    "clk", "i_clk", "clk_i", "CLK", "iClk", "ClkIn", "clk_in", "sys_clk", "sysclk", "aclk",
    "clock", "i_clock", "horloge", "h_horloge_i", "takt", "clk100", "clk_100mhz", "ck", "pi_clk",
])
def test_clock_names(name):
    assert _clock(_ports(name, "en", "start", "rst")) == [name]


@pytest.mark.parametrize("name", [
    "rst", "rst_n", "i_rst", "rst_i", "i_rst_n", "rstn", "nrst", "reset", "resetn", "aresetn",
    "RST_N", "nReset", "raz", "raz_n", "i_raz", "arst", "srst", "presetn", "rst_ni", "reset_b",
])
def test_reset_names(name):
    assert _reset(_ports("clk", "en", "start", name)) == [name]


@pytest.mark.parametrize("name", [
    "clk_en", "clk_div", "clk_sel", "rst_done", "first", "burst", "block", "lock", "start",
    "data_in", "en", "valid",
])
def test_no_false_positives(name):
    unit = _ports(name)
    assert _clock(unit) == [] and _reset(unit) == []


def test_multi_bit_and_outputs_are_not_clocks():
    unit = _verilog("module m(input [3:0] clk, output clk_o, input reset); endmodule")[0]
    assert _clock(unit) == []


def test_edges_decide_over_names():
    unit = _verilog("""
        module m(input wire a, input wire b, input wire [7:0] d, output reg [7:0] q);
          always @(posedge a or negedge b)
            if (!b) q <= 0; else q <= d;
        endmodule""")[0]
    assert _clock(unit) == ["a"]
    assert _reset(unit) == ["b"]


def test_non_ansi_ports():
    unit = _verilog("""
        module m(clk, rst_n, d, q);
          input clk, rst_n;
          input [7:0] d;
          output [7:0] q;
        endmodule""")[0]
    assert {p.name: p.direction for p in unit.ports} == {"clk": "input", "rst_n": "input", "d": "input", "q": "output"}
    assert unit.port("d").wide and not unit.port("clk").wide
    assert _clock(unit) == ["clk"] and _reset(unit) == ["rst_n"]


def test_vhdl_async_reset_and_clock():
    unit = _vhdl("""
        entity compteur is
          generic (N : integer := 8);
          port (
            H, RAZ : in std_logic;   -- horloge, remise a zero
            Q : out std_logic_vector(N-1 downto 0)
          );
        end entity;
        architecture rtl of compteur is
        begin
          process(H, RAZ) begin
            if RAZ = '1' then Q <= (others => '0');
            elsif rising_edge(H) then Q <= Q;
            end if;
          end process;
        end architecture;""")[0]
    assert unit.name == "compteur"
    assert _clock(unit) == ["H"]
    assert _reset(unit) == ["RAZ"]


def test_top_module_is_the_one_not_instantiated():
    units = _verilog("""
        module leaf(input clk, output q); endmodule
        module top_wrapper(input clk, output q);
          leaf #(.W(2)) u_leaf (.clk(clk), .q(q));
        endmodule
        module tb_top; top_wrapper dut(.clk(), .q()); endmodule
    """)
    assert [c.value for c in h.top_module_candidates(units)] == ["top_wrapper"]


def test_several_tops_are_proposed():
    units = _verilog("module a(input x); endmodule module b(input y); endmodule")
    assert sorted(c.value for c in h.top_module_candidates(units)) == ["a", "b"]


def test_ambiguous_clocks_are_all_proposed():
    unit = _ports("clk_a", "clk_b", "rst")
    assert sorted(_clock(unit)) == ["clk_a", "clk_b"]


def test_split_words():
    assert h.split_words("i_SysClk2x_n") == ["i", "sys", "clk", "2", "x", "n"]


######################################
# Parameters
######################################

def _params(text, filename, section=None):
    return [(p.name, p.value) for p in h.detect_parameters(text, filename, section)]


def _between(text, start, stop):
    at = text.index(start) + len(start)
    return at, text.index(stop, at)


@pytest.mark.parametrize("filename,text,expected", [
    ("m.sv", "module m #(parameter int WIDTH = 8, DEPTH = 2**4, parameter logic [3:0] INIT = 4'hA)(); endmodule",
     [("WIDTH", "8"), ("DEPTH", "2**4"), ("INIT", "4'hA")]),
    ("m.v", "`define BAUD 115200 // baud\nmodule m; localparam L = 3; endmodule", [("BAUD", "115200"), ("L", "3")]),
    ("e.vhd", "entity e is generic (N : integer := 8; -- n\n MODE : string := \"fast\"); end;\n"
              "package p is constant DEPTH : positive := 16; end;",
     [("N", "8"), ("MODE", '"fast"'), ("DEPTH", "16")]),
    ("Top.scala", "class ALU(val width: Int = 32, depth: Int = 4) extends Module {\n  val stages = 3\n}",
     [("width", "32"), ("depth", "4"), ("stages", "3")]),
    ("top.py", "def __init__(self, width=8, reset: int = 0):\n    pass\nWIDTH = 16  # c\n",
     [("width", "8"), ("reset", "0"), ("WIDTH", "16")]),
    ("fir.cpp", "#define N_TAPS 16\nconst int COEF_W = 12;\nstatic constexpr unsigned DATA_W = 18;",
     [("N_TAPS", "16"), ("COEF_W", "12"), ("DATA_W", "18")]),
    ("Top.hs", "type Width = 16\ndepth = 4\n", [("Width", "16"), ("depth", "4")]),
    ("cfg.tcl", "set CLK_PERIOD 10.0\n# set OLD 1\n", [("CLK_PERIOD", "10.0")]),
    ("params.yml", "width: 8\ndepth: 16\n", [("width", "8"), ("depth", "16")]),
    ("config.mk", "WIDTH ?= 8\nDEPTH := 4\n", [("WIDTH", "8"), ("DEPTH", "4")]),
    # an unknown extension keeps literal values only
    ("params.txt", "WIDTH = 8\nNAME = some text\n", [("WIDTH", "8")]),
])
def test_detect_parameters(filename, text, expected):
    assert _params(text, filename) == expected


def test_named_arguments_keep_literals_only():
    text = "module top; alu #(.WIDTH(16), .DEPTH(4)) u (.clk(clk)); endmodule"
    assert _params(text, "top.v") == [("WIDTH", "16"), ("DEPTH", "4")]
    text = 'u: entity work.alu generic map (WIDTH => 16, MODE => "fast") port map (clk => clk);'
    assert _params(text, "top.vhd") == [("WIDTH", "16"), ("MODE", '"fast"')]


@pytest.mark.parametrize("filename,text,start,stop,expected", [
    ("ALUTop.scala", "class ALUTop(BITS: Int) extends Module {}\nobject A { emit(new ALUTop(8), x) }",
     "new ALUTop(", ")", [("BITS", "8")]),
    ("t.v", "module alu #(parameter W = 8, parameter D = 2)(); endmodule\nmodule t; alu #(16, 4) u(); endmodule",
     "alu #(16", ")", None),
    ("t.vhd", "entity alu is generic (WIDTH : integer := 8; DEPTH : natural := 2); end;\n"
              "architecture a of t is begin u: entity work.alu generic map (16, 4); end;",
     "generic map (", ")", [("WIDTH", "16"), ("DEPTH", "4")]),
    ("t.cpp", "void fir(int taps, int width);\nint main() { fir(16, 12); }", "{ fir(", ")",
     [("taps", "16"), ("width", "12")]),
    ("t.py", "Other(8, \"x\")", "Other(", ")", [("param1", "8"), ("param2", '"x"')]),
])
def test_positional_arguments_take_the_names_of_the_signature(filename, text, start, stop, expected):
    if start == "alu #(16":
        at = text.index(start) + len("alu #(")
        section = (at, text.index(stop, at))
        expected = [("W", "16"), ("D", "4")]
    else:
        section = _between(text, start, stop)
    assert _params(text, filename, section) == expected


def test_template_puts_variables_in_place_of_values():
    text = "// begin\n  parameter WIDTH = 8,\n  parameter DEPTH = 4\n// end"
    section = _between(text, "// begin", "// end")
    params = h.detect_parameters(text, "m.v", section)
    assert h.parameter_template(text, section, params[:1]) == "\n  parameter WIDTH = ${WIDTH},\n  parameter DEPTH = 4\n"


def test_relevance_puts_derived_and_local_ones_last():
    params = h.detect_parameters("module m #(parameter W = 8, parameter X = W*2)(); localparam L = 3; endmodule", "m.v")
    relevance = dict((p.name, h.parameter_relevance(p, params)) for p in params)
    assert relevance["W"] >= 7 > relevance["X"] and relevance["L"] < 7


######################################
# Delimiters
######################################

from odatix.components.replace_params import replace_content


@pytest.mark.parametrize("filename,text", [
    ("m.v", "module m #(\n  parameter WIDTH = 8,\n  parameter DEPTH = 8, // d\n  parameter INIT  = 8\n)();\nendmodule"),
    ("e.vhd", "entity e is generic (\n  N : integer := 8;\n  M : integer := 8\n); end;"),
    ("ALUTop.scala", "class ALUTop(BITS: Int) extends Module {\n  val x = Wire(UInt(BITS.W))\n}\n"
                     "object A extends App { emit(new ALUTop(8), Array(\"-o\")) }"),
    ("cfg.tcl", "set A 8\nset B 8\n"),
])
def test_auto_delimiters_replace_exactly_the_value(filename, text):
    params = h.detect_parameters(text, filename)
    assert params
    for param in params:
        start, stop = h.auto_delimiters(text, param.start, param.end, param.name)
        replaced, found = replace_content(text, "999", start, stop, False, keep_lines=False)
        assert found
        assert replaced == text[:param.start] + "999" + text[param.end:], param.name


def test_auto_delimiters_name_the_parameter_when_they_can():
    text = "module m #(\n  parameter WIDTH = 8,\n  parameter DEPTH = 8\n)(); endmodule"
    params = h.detect_parameters(text, "m.v")
    assert [h.auto_delimiters(text, p.start, p.end, p.name)[0] for p in params] == ["WIDTH = ", "DEPTH = "]


def test_vhdl_aggregates_are_not_parameters():
    assert _params("architecture a of e is begin q <= (others => '0'); end;", "e.vhd") == []
