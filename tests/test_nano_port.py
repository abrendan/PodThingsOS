import unittest
from pathlib import Path
import test_coverflow_refinements as native

ROOT=Path(__file__).resolve().parents[1]


class NanoPort(unittest.TestCase):
    run_c=native.Refinements.run_c

    def test_real_diagnostic_write_entry_rejects_writes(self):
        code=native.function(
            "rockbox-firmware/firmware/target/arm/s5l8702/ipodnano3g/nand-check-nano3g.c",
            "nand_write_sectors")
        self.run_c("""
#include <stdint.h>
typedef uint64_t sector_t;
#define IF_MD(...)
""" + code + """
int main(void) {
    unsigned char data[2048]; memset(data,0x5a,sizeof(data));
    assert(nand_write_sectors(0,1,data)==-1);
    assert(nand_write_sectors(123456,100,data)==-1);
    assert(nand_write_sectors(0,0,NULL)==-1);
    for(size_t i=0;i<sizeof(data);i++) assert(data[i]==0x5a);
}
""")

    def test_nano_is_not_aliased_to_classic_or_forced_writable(self):
        config=(ROOT/"rockbox-firmware/firmware/export/config/ipodnano3g.h").read_text()
        self.assertIn('#define BOOTFILE "podthingsos." BOOTFILE_EXT',config)
        self.assertIn('#define BOOTDIR "/.podthingsloader"',config)
        self.assertIn("#define PODTHINGS_OS 1",config)
        self.assertNotIn("#define IPOD_6G",config)
        self.assertNotIn("#define NAND_WRITABLE_ID",config)
        build=(ROOT/"scripts/rockbox-build.sh").read_text()
        self.assertIn('-DNAND_CHECK',build)
        self.assertNotIn("NAND_WRITABLE_ID",build)

    def test_nano_uses_shared_handoff_without_video_ata_barrier(self):
        source=(ROOT/"rockbox-firmware/bootloader/ipod-s5l87xx.c").read_text()
        self.assertIn('#if defined(IPOD_6G) || defined(IPOD_NANO3G)\n#include "podthings_boot.h"',source)
        protocol=(ROOT/"rockbox-firmware/firmware/common/podthings_boot.c").read_text()
        self.assertIn("#if (defined(IPOD_VIDEO) || defined(IPOD_COLOR)) && !defined(SIMULATOR)",protocol)
        self.assertNotIn("ata_flush_for_handoff", source)

    def test_write_policy_is_explicit_and_diagnostic_always_wins(self):
        policy=native.function(
            "rockbox-firmware/firmware/target/arm/s5l8702/ipodnano3g/nand-target.h",
            "nand_geometry_writes_allowed")
        for defines, unvalidated, validated in (
            ("", 0, 1),
            ("#define PODTHINGS_NANO_UNVALIDATED_WRITES\n", 1, 1),
            ("#define PODTHINGS_NANO_UNVALIDATED_WRITES\n#define NAND_CHECK\n", 0, 0),
            ("#define PODTHINGS_NANO_UNVALIDATED_WRITES\n#define NAND_TEST_READONLY\n", 0, 0),
        ):
            with self.subTest(defines=defines):
                self.run_c(defines + """
struct nand_geometry {bool validated;};
""" + policy + f"""
int main(void) {{
    struct nand_geometry g={{false}};
    assert(nand_geometry_writes_allowed(&g)=={unvalidated});
    g.validated=true;
    assert(nand_geometry_writes_allowed(&g)=={validated});
}}
""")

    def test_experimental_table_still_requires_id_and_bank_match(self):
        source=(ROOT/"rockbox-firmware/firmware/target/arm/s5l8702/ipodnano3g/nand-nano3g.c").read_text()
        self.assertIn("#if defined(NAND_CHECK) || defined(PODTHINGS_NANO_UNVALIDATED_WRITES)",source)
        self.assertIn("nand_chip_table[i].banks == nand_banks",source)
        self.assertIn("return NAND_ERR_UNSUPPORTED;",source)
        ftl=(ROOT/"rockbox-firmware/firmware/target/arm/s5l8702/ipodnano3g/ftl-nano3g.c").read_text()
        self.assertIn("if (!nand_geometry_writes_allowed(geo))",ftl)
        self.assertIn("ftl_writable = false;",ftl)

    def test_recognized_chip_table_in_safe_and_experimental_builds(self):
        source=(ROOT/"rockbox-firmware/firmware/target/arm/s5l8702/ipodnano3g/nand-nano3g.c").read_text()
        start=source.index("struct nand_chip_info\n")
        end=source.index("/* Physical blocks per bank",start)
        declarations=source[start:end]
        for defines, count in (("",4),("#define PODTHINGS_NANO_UNVALIDATED_WRITES\n",18),
                               ("#define NAND_CHECK\n",18)):
            with self.subTest(defines=defines):
                self.run_c("#include <stdint.h>\n"+defines+declarations+f"""
int main(void) {{
    assert(sizeof(nand_chip_table)/sizeof(nand_chip_table[0])=={count});
    int matches=0;
    for(unsigned i=0;i<sizeof(nand_chip_table)/sizeof(nand_chip_table[0]);i++)
        if(nand_chip_table[i].id==0x3E94D52C && nand_chip_table[i].banks==2) {{
            matches++;
            assert(!nand_chip_table[i].validated);
        }}
    assert(matches=={int(count==18)});
}}
""")


if __name__=="__main__":
    unittest.main()
