#include "WeaponMotionState.h"
#include <cmath>
#include <iostream>
#include <limits>
#include <cstdlib>

using namespace AnabiosisWeapons;

static int Checks = 0;
static void Check(bool Passed, const char* Name)
{
    ++Checks;
    if (!Passed) { std::cerr << "FAIL: " << Name << '\n'; std::exit(1); }
}

static MotionFrame SimulateAim(int FPS)
{
    MotionState State;
    MotionInput Input;
    Input.Aiming = true;
    Input.DeltaSeconds = 1.0 / FPS;
    MotionFrame Result;
    for (int I=0; I<FPS; ++I) Result = State.Update(Input);
    return Result;
}

int main()
{
    Check(std::abs(SimulateAim(30).AimAlpha - SimulateAim(144).AimAlpha)<0.00001,
          "aim interpolation must not depend on FPS");
    Check(SimulateAim(60).AimAlpha>.99, "aim reaches its target");

    MotionState State;
    MotionInput Input;
    Input.DeltaSeconds=.02;
    Input.Speed=500;
    Input.Trigger=true;
    auto Frame=State.Update(Input);
    Check(Frame.Attacking && Frame.FirePulse, "flamethrower starts on the first input frame");
    for (int I=0; I<12; ++I) Frame=State.Update(Input);
    Check(Frame.Attacking && std::abs(Frame.WalkSide)+std::abs(Frame.WalkUp)>.01,
          "walking and attack coexist");
    Input.Aiming=true;
    for (int I=0; I<30; ++I) Frame=State.Update(Input);
    Check(Frame.Attacking && Frame.AimAlpha>.99, "aiming does not cancel firing or movement");
    Input.Trigger=false;
    Frame=State.Update(Input);
    Check(!Frame.Attacking && !Frame.FirePulse, "release stops the stream immediately");

    Input.Trigger=true;
    State.Update(Input);
    Input.SelectWeapon=1;
    Frame=State.Update(Input);
    Check(Frame.Switching && !Frame.Attacking, "switch cancels old attack");
    Input.SelectWeapon=-1;
    int Swaps=0;
    for (int I=0; I<30; ++I)
    {
        Frame=State.Update(Input);
        Swaps += Frame.WeaponChanged;
        Check(!Frame.Attacking, "held trigger cannot leak through a switch");
    }
    Check(Frame.WeaponIndex==1 && !Frame.Switching && Swaps==1, "one switch commits once");
    Input.Trigger=false; State.Update(Input);
    Input.Trigger=true;
    Frame=State.Update(Input);
    Check(Frame.FirePulse && Frame.Attacking, "water pistol fires after release and repress");
    Input.Trigger=false;
    Frame=State.Update(Input);
    Check(!Frame.Attacking, "water stream is cancelled immediately by release");

    for (int FPS : {30,144})
    {
        MotionState Water;
        MotionInput In;
        In.DeltaSeconds=1.0/FPS;
        In.SelectWeapon=1;
        Water.Update(In); In.SelectWeapon=-1;
        for (int I=0; I<FPS; ++I) Water.Update(In);
        In.Trigger=true;
        int Shots=0;
        for (int I=0; I<FPS; ++I) Shots+=Water.Update(In).FirePulse;
        Check(Shots==5, "held water pistol repeats at 0.24 seconds across frame rates");
    }

    Input.Trigger=false;
    Input.Aiming=false;
    Input.Speed=0;
    Input.SelectWeapon=0;
    State.Update(Input); Input.SelectWeapon=-1;
    for (int I=0; I<100; ++I) Frame=State.Update(Input);
    Check(Frame.WeaponIndex==0 && Frame.AimAlpha<.0001, "lowered aim returns smoothly to hip pose");
    for (double Dt : {-1.0,0.0,std::numeric_limits<double>::quiet_NaN(),
                     std::numeric_limits<double>::infinity(),100.0})
    {
        Input.DeltaSeconds=Dt;
        Frame=State.Update(Input);
        Check(std::isfinite(Frame.WalkSide) && std::isfinite(Frame.RecoilBack)
              && std::isfinite(Frame.AimAlpha), "invalid and hitch delta times cannot poison the pose");
    }
    MotionState Raising;
    MotionInput Late;
    Late.DeltaSeconds=.02;
    Late.SelectWeapon=1;
    Raising.Update(Late);
    Late.SelectWeapon=-1;
    for (int I=0; I<20; ++I) Raising.Update(Late);
    Late.SelectWeapon=0;
    Raising.Update(Late);
    Late.SelectWeapon=-1;
    for (int I=0; I<4; ++I) Raising.Update(Late);
    Late.Trigger=true;
    do { Frame=Raising.Update(Late); } while (Frame.Switching);
    Check(Frame.Attacking && Frame.FirePulse, "flame starts its attack animation when a new press is held through raising");
    std::cout << "PASS: " << Checks << " weapon motion/state checks\n";
}
