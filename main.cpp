#include <iostream>
#include <boost/dynamic_bitset.hpp>
#include <gmp.h>
#include <stdio.h>
#include <iostream>
#include <mp++/mp++.hpp>
#include <mgl2/fltk.h>
#include "orgf.h"

using int_t = mppp::integer<1>;

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
    boost::dynamic_bitset<> db(10);
    db.set(3);
    std::cout << db<<std::endl;
    std::cout << "Hello, from ProductAutomata!\n";
    int_t n{42};
    std::cout << n << '\n';
    mglFLTK gr(graph, "MathGL demo window title");
    return gr.Run();
}





