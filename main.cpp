#include <iostream>
#include <boost/dynamic_bitset.hpp>
#include <stdio.h>
#include <iostream>
//#include <mp++/mp++.hpp>
#include <mgl2/fltk.h>
//#include "urgf.h"
//#include "urgfdag.h"
#include "RegPDFA.h"
//#include"flint/arb.h"
//#include"flint/flint.h"

//using int_t = mppp::integer<1>;

int graph(mglGraph *gr) {
    gr->Title("MathGL Demo");
    gr->SetOrigin(0, 0);
    gr->SetRanges(0, 10, -2.5, 2.5);
    gr->FPlot("sin(1.7*2*pi*x) + sin(1.9*2*pi*x)", "r-4");
    gr->Axis();
    gr->Grid();
    return 0;
}
int main()
{
    // boost::dynamic_bitset<> db(10);
    // db.set(3);
    // std::cout << db<<std::endl;
    // std::cout << "Hello, from ProductAutomata!\n";
    //int_t n{42};
    //std::cout << n << '\n';
    urgf::test();
    // urgfdag::test();
    RegPDFA pdfa;
    pdfa.initwithstring("5 001-00,000-0,01-0,10-_,11-1");
    RegPDFA pdfa2;
    pdfa2.initwithstring("5 000-00,001-0,01-0,10-_,11-1");
    auto pdfa3 = pdfa.cartesian_product(pdfa2);
    std::cout << "PDFA3: " << pdfa3.to_string() << std::endl;
    // mglFLTK gr(graph, "MathGL
    cout << pdfa.to_string() << endl;
    // mglFLTK gr(graph, "MathGL demo window title");
    // return gr.Run();
    return 0;
}





