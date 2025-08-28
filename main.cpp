#include <iostream>
#include <boost/dynamic_bitset.hpp>
#include <stdio.h>
#include <iostream>
//#include <mp++/mp++.hpp>
//#include <mgl2/fltk.h>
#include "rgfdag.h"
#include "RegPDFAGenerator.h"
#include "FullBinaryTreeGenerator.h"
#include "VectorNGenerator.h"
//#include "RegPDFA.h"
//#include"flint/arb.h"
//#include"flint/flint.h"

//using int_t = mppp::integer<1>;
using boost::to_string;
// int graph(mglGraph *gr) {
//     gr->Title("MathGL Demo");
//     gr->SetOrigin(0, 0);
//     gr->SetRanges(0, 10, -2.5, 2.5);
//     gr->FPlot("sin(1.7*2*pi*x) + sin(1.9*2*pi*x)", "r-4");
//     gr->Axis();
//     gr->Grid();
//     return 0;
// }
int main()
{
    // boost::dynamic_bitset<> db(10);
    // db.set(3);
    // std::cout << db<<std::endl;
    // std::cout << "Hello, from ProductAutomata!\n";
    //int_t n{42};
    //std::cout << n << '\n';
    // urgf::test();
    RegPDFA pdfa;
    pdfa.initwithstring("001-00,000-0,01-0,10-_,11-1");
    RegPDFA pdfa2;
    pdfa2.initwithstring("000-00,001-0,01-0,10-_,11-1");
    auto pdfa3 = pdfa.cartesian_product(pdfa2);
    RegPDFA pdfa4;
    pdfa4.initwithstring("00-_,01-0,10-0,11-1");
    dynamic_bitset<> state1,state2,state3;
    state3 = dynamic_bitset<>(0);
    state2.push_back(false);
    state1.push_back(false);
    state1.push_back(false);
    string state1_str;
    to_string(state1, state1_str);
    cout<< "State1: " << state1_str << endl;
    string state2_str;
    to_string(state2, state2_str);
    cout<< "State2: " << state2_str << endl;
    std::cout << "PDFA3: " << pdfa3.to_string() << std::endl;
    auto urgfdag1 = rgfdag<urgf>::compute_rgfdag(pdfa3, state1);
    std::cout << "Urgfdag1: " << urgfdag1->to_string() << std::endl;
    auto urgfres = urgfdag1->resolvetorgf();
    std::cout << "Urgfres: " << urgfres.to_string() << std::endl;
    auto urgfdag2 = rgfdag<brgf>::compute_rgfdag(pdfa4, state2);
    std::cout << "Urgfdag2: " << urgfdag2->to_string() << std::endl;
    auto urgfres2 = urgfdag2->resolvetorgf();
    std::cout << "Urgfres2: " << urgfres2.to_string() << std::endl;
    delete urgfdag1;
    delete urgfdag2;
    cout << pdfa.to_string() << endl;
    FullBinaryTreeGenerator::test();
    VectorNGenerator::test();
    RegPDFAGenerator::test();
    // urgfdag::test();
    // mglFLTK gr(graph, "MathGL demo window title");
    // return gr.Run();
    return 0;
}





