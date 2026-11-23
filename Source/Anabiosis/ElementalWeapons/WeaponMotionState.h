#pragma once

#include <algorithm>
#include <cmath>

// Engine-independent state used by the actual first-person component and the
// standalone regression tests. Distances are centimetres; angles are degrees.
namespace AnabiosisWeapons
{
struct MotionInput
{
    double DeltaSeconds = 0;
    double Speed = 0;
    double TurnYawRate = 0;
    double TurnPitchRate = 0;
    bool Aiming = false;
    bool Trigger = false;
    int SelectWeapon = -1;
};

struct MotionFrame
{
    int WeaponIndex = 0;
    bool WeaponChanged = false;
    bool Switching = false;
    bool Attacking = false;
    bool FirePulse = false;
    double AimAlpha = 0;
    double SwitchDrop = 0;
    double WalkSide = 0;
    double WalkUp = 0;
    double RecoilBack = 0;
    double RecoilPitch = 0;
    double SwayYaw = 0;
    double SwayPitch = 0;
    double Roll = 0;
};

class MotionState
{
    int ActiveWeapon = 0;
    int PendingWeapon = -1;
    bool SwapCommitted = false;
    bool ReleaseRequired = false;
    bool PreviousFiring = false;
    double SwitchTime = 0;
    double Aim = 0;
    double Movement = 0;
    double FireBlend = 0;
    double Phase = 0;
    double Clock = 0;
    double AttackAge = 100;
    double WaterCooldown = 0;
    double Yaw = 0;
    double Pitch = 0;

    static double Finite(double Value) { return std::isfinite(Value) ? Value : 0; }
    static double Smooth(double Current, double Target, double Rate, double Dt)
    {
        return Target + (Current-Target)*std::exp(-Rate*Dt);
    }

public:
    MotionFrame Update(const MotionInput& Input)
    {
        constexpr double Pi = 3.14159265358979323846;
        constexpr double SwitchDuration = .32;
        const double Dt = std::clamp(Finite(Input.DeltaSeconds),0.0,.25);
        Clock += Dt;
        AttackAge += Dt;
        MotionFrame Frame;

        const int Desired = PendingWeapon>=0 ? PendingWeapon : ActiveWeapon;
        if (Input.SelectWeapon>=0 && Input.SelectWeapon<=1 && Input.SelectWeapon!=Desired)
        {
            PendingWeapon=Input.SelectWeapon;
            SwitchTime=0;
            SwapCommitted=false;
            ReleaseRequired=true;
            WaterCooldown=0;
        }
        if (!Input.Trigger) ReleaseRequired=false;
        if (PendingWeapon>=0)
        {
            SwitchTime+=Dt;
            if (!SwapCommitted && SwitchTime>=.14)
            {
                Frame.WeaponChanged=ActiveWeapon!=PendingWeapon;
                ActiveWeapon=PendingWeapon;
                SwapCommitted=true;
                AttackAge=100;
            }
            if (SwitchTime>=SwitchDuration) PendingWeapon=-1;
        }
        Frame.Switching=PendingWeapon>=0;
        Frame.WeaponIndex=ActiveWeapon;
        Frame.SwitchDrop=Frame.Switching ? std::sin(Pi*SwitchTime/SwitchDuration) : 0;
        const bool CanFire=Input.Trigger && !ReleaseRequired && !Frame.Switching;
        if (CanFire)
        {
            if (ActiveWeapon==0)
            {
                Frame.FirePulse=!PreviousFiring;
                Frame.Attacking=true;
            }
            else
            {
                WaterCooldown-=Dt;
                if (WaterCooldown<=1e-9)
                {
                    Frame.FirePulse=true;
                    AttackAge=0;
                    do { WaterCooldown+=.24; } while (WaterCooldown<=1e-9);
                }
                Frame.Attacking=AttackAge<.10;
            }
        }
        else
        {
            WaterCooldown=0;
        }
        PreviousFiring=CanFire;
        Aim=Smooth(Aim,Input.Aiming && !Frame.Switching ? 1.0 : 0.0,18,Dt);
        Movement=Smooth(Movement,std::clamp(Finite(Input.Speed)/600.0,0.0,1.2),9,Dt);
        FireBlend=Smooth(FireBlend,CanFire && ActiveWeapon==0 ? 1.0 : 0.0,24,Dt);
        Phase=std::fmod(Phase+Dt*10.5*Movement,2*Pi);
        Yaw=Smooth(Yaw,std::clamp(Finite(Input.TurnYawRate)/180.0,-1.0,1.0),16,Dt);
        Pitch=Smooth(Pitch,std::clamp(Finite(Input.TurnPitchRate)/180.0,-1.0,1.0),16,Dt);
        const double Steady=1-.8*Aim;
        Frame.AimAlpha=Aim;
        Frame.WalkSide=.65*Movement*Steady*std::sin(Phase);
        Frame.WalkUp=.45*Movement*Steady*(std::cos(2*Phase)-1);
        const double Kick=std::exp(-AttackAge*24)*(1-std::exp(-AttackAge*140));
        Frame.RecoilBack=ActiveWeapon==0 ? FireBlend*(1.15+.1*std::sin(Clock*41)) : 2.6*Kick;
        Frame.RecoilPitch=ActiveWeapon==0 ? FireBlend*(.55+.12*std::sin(Clock*33)) : 3.5*Kick;
        Frame.SwayYaw=-.9*Yaw*Steady;
        Frame.SwayPitch=.7*Pitch*Steady;
        Frame.Roll=-.6*std::sin(Phase)*Movement*Steady-Frame.SwitchDrop*25;
        return Frame;
    }
};
}
