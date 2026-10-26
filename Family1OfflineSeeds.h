#pragma once
#include <string>
#include <vector>

// Graph-only bootstrap catalogue. No word pairs or score labels are embedded.
// Sources: results/family1-m1-m6/maximizers.jsonl, family1-m7/maximizers.jsonl,
// and the two documented eight-state experimental graphs. These seeds do not
// certify a search run's coverage or the scores computed by that run.
namespace family1::offline_seeds {
inline std::vector<std::string> keys_by_size(unsigned int m)
{
    switch (m) {
    case 1: return {"0000"};
    case 2: return {"00010001"};
    case 3: return {"000101020001", "010200010102"};
    case 4: return {"0102000201030003"};
    case 5: return {"00010203000103040204", "00010203000301040204",
                    "01020003010203040004", "01020003010402030104", "01020003030400030104"};
    case 6: return {"000102030304020500010405", "010200030405020300010405"};
    case 7: return {"0001020302030405000604060105", "0001020304050406050600010203",
                    "0102000301040204050600030506", "0102000304050106000304050206",
                    "0102010203040005030604060005", "0102010203040005050600060304",
                    "0102020304050006000604050103", "0102030405060001000203040506"};
    case 8: return {"01020002030403040506000705070206", "01020003040501060003020705060407"};
    default: return {};
    }
}
}
